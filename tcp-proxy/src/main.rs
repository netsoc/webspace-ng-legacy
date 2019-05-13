use std::num;
use std::ptr;
use std::collections::HashMap;
use std::thread;
use std::io::{self, Read, Write};
use std::net::{AddrParseError, Ipv4Addr, SocketAddr, TcpStream, TcpListener};
use std::os::unix::io::{AsRawFd, RawFd};

use quick_error::quick_error;
use nix::errno::Errno;
use nix::sys::time::TimeSpec;
use nix::sys::signal::{Signal, SigSet};
use nix::sys::signalfd::SignalFd;
use nix::unistd;
use nix::poll::{EventFlags, PollFd, poll};
use nix::sys::eventfd::{EfdFlags, eventfd};
use bytes::{Buf, BufMut, BytesMut};
use futures::future::Future;
use futures::stream::Stream;
use tokio::runtime::current_thread::block_on_all;

pub fn ppoll(fds: &mut [PollFd], timeout: Option<TimeSpec>, sigmask: SigSet) -> nix::Result<libc::c_int> {
    let res = unsafe {
        libc::ppoll(fds.as_mut_ptr() as *mut libc::pollfd,
                    fds.len() as libc::nfds_t,
                    match timeout {
                        Some(t) => t.as_ref(),
                        None => ptr::null(),
                    },
                    sigmask.as_ref())
    };
    Errno::result(res)
}

quick_error! {
    #[derive(Debug)]
    pub enum Error {
        Io(err: io::Error) {
            from()
            cause(err)
            description(err.description())
            display("{}", err)
        }
        IntParse(err: num::ParseIntError) {
            from()
            cause(err)
            description(err.description())
            display("{}", err)
        }
        Os(err: nix::Error) {
            from()
            cause(err)
            description(err.description())
            display("{}", err)
        }
        Hyper(err: hyper::Error) {
            from()
            cause(err)
            description(err.description())
            display("{}", err)
        }
        Xmlrpc(err: xmlrpc::Error) {
            from()
            cause(err)
            description(err.description())
            display("{}", err)
        }
        AddrParse(err: AddrParseError) {
            from()
            cause(err)
            description(err.description())
            display("{}", err)
        }
        Other(err: Box<std::error::Error + Sync + Send>) {
            from()
            cause(&**err)
            description(err.description())
            display("{}", err)
        }

        Quit
        InvalidCommand(reason: &'static str) {
            description("invalid command")
            display("invalid command: {}", reason)
        }
        AlreadyForwarded(port: u16) {
            description("port already forwarded")
            display("port {} already forwarded", port)
        }
        NotForwarded(port: u16) {
            description("port not forwarded")
            display("port {} already forwarded", port)
        }
        Rpc(reason: String) {
            description("xmlrpc error")
            display("xmlrpc error: {}", reason)
        }
        ConnClosed
    }
}
type Result<T> = std::result::Result<T, Error>;

struct UnixXmlrpc {
    uri: hyper::Uri,
}
impl UnixXmlrpc {
    pub fn new(uri: hyper::Uri) -> UnixXmlrpc {
        UnixXmlrpc {
            uri,
        }
    }
}
impl xmlrpc::Transport for UnixXmlrpc {
    type Stream = bytes::buf::Reader<hyper::Chunk>;
    fn transmit(self, request: &xmlrpc::Request) -> std::result::Result<Self::Stream, Box<std::error::Error + Send + Sync>> {
        let mut body = Vec::new();
        request.write_as_xml(&mut body).unwrap();

        let client = hyper::Client::builder()
            .keep_alive(true)
            .build::<_, hyper::Body>(hyperlocal::UnixConnector::new());
        let req = hyper::Request::post(self.uri)
            .header("User-Agent", "Rust-xmlrpc/0.1")
            .header("Content-Type", "text/xml; charset=utf-8")
            .header("Content-Length", body.len())
            .body(body.into())?;


        let res = client
            .request(req)
            .map_err(|e| format!("{}", e))
            .and_then(|res| {
                if res.status().is_client_error() || res.status().is_server_error() {
                    return Err(format!("http error status: {}", res.status()));
                }
                Ok(res
                   .into_body()
                   .concat2()
                   .map_err(|e| format!("{}", e)))
            })
            .flatten();

        let res_body = block_on_all(res)?;
        Ok(res_body.reader())
    }
}

struct ForwardingConn {
    src: TcpStream,
    src_buf: BytesMut,

    dst: TcpStream,
    dst_buf: BytesMut,
}
impl ForwardingConn {
    pub fn new(src: TcpStream, dst: TcpStream) -> ForwardingConn {
        ForwardingConn {
            src,
            src_buf: BytesMut::with_capacity(4096),
            dst,
            dst_buf: BytesMut::with_capacity(4096),
        }
    }

    pub fn addrs(&self) -> Result<(SocketAddr, SocketAddr)> {
        Ok((self.src.local_addr()?, self.dst.local_addr()?))
    }
    pub fn add_polls(&mut self, list: &mut Vec<PollFd>) {
        let mut src_flags = EventFlags::POLLPRI;
        let mut dst_flags = EventFlags::POLLPRI;

        if self.src_buf.is_empty() {
            src_flags.insert(EventFlags::POLLIN);
        } else {
            dst_flags.insert(EventFlags::POLLOUT);
        }
        if self.dst_buf.is_empty() {
            dst_flags.insert(EventFlags::POLLIN);
        } else {
            src_flags.insert(EventFlags::POLLOUT);
        }

        list.push(PollFd::new(self.src.as_raw_fd(), src_flags));
        list.push(PollFd::new(self.dst.as_raw_fd(), dst_flags));
    }
    pub fn update(&mut self, src: PollFd, dst: PollFd) -> Result<()> {
        let src_flags = src.revents().expect("src flags");
        if src_flags.contains(EventFlags::POLLOUT) {
            self.src.write(&self.dst_buf)?;
            self.dst_buf.clear();
        } else if src_flags.contains(EventFlags::POLLIN) {
            unsafe {
                let read = self.src.read(self.src_buf.bytes_mut())?;
                if read == 0 {
                    return Err(Error::ConnClosed);
                }
                self.src_buf.advance_mut(read);
            }
        }

        let dst_flags = dst.revents().expect("dst flags");
        if dst_flags.contains(EventFlags::POLLOUT) {
            self.dst.write(&self.src_buf)?;
            self.src_buf.clear();
        } else if dst_flags.contains(EventFlags::POLLIN) {
            unsafe {
                let read = self.dst.read(self.dst_buf.bytes_mut())?;
                if read == 0 {
                    return Err(Error::ConnClosed);
                }
                self.dst_buf.advance_mut(read);
            }
        }

        Ok(())
    }
}

struct ForwardingInner {
    eport: u16,
    user: String,
    iport: u16,

    listener: TcpListener,
    conns: HashMap<(SocketAddr, SocketAddr), ForwardingConn>,
    stop_fd: RawFd,
}
impl ForwardingInner {
    pub fn new(stop_fd: RawFd, eport: u16, user: String, iport: u16) -> Result<ForwardingInner> {
        let listener = TcpListener::bind(("::", eport))?;
        Ok(ForwardingInner {
            eport,
            user,
            iport,

            listener,
            conns: HashMap::new(),
            stop_fd, 
        })
    }

    fn get_ip(&self) -> Result<Ipv4Addr> {
        let res = xmlrpc::Request::new("boot_and_ip")
            .arg(self.user.as_ref())
            .call(UnixXmlrpc::new(hyperlocal::Uri::new("/var/lib/webspace-ng/unix.socket", "/RPC2").into()))?;
        match res.as_str() {
            Some(ip) => Ok(ip.parse()?),
            None => Err(Error::Rpc("server did not return a string".to_string())),
        }
    }
    fn new_conn(&mut self) -> Result<()> {
        let (src, src_addr) = self.listener.accept()?;

        let dst_addr: SocketAddr = (self.get_ip()?, self.iport).into();
        let dst = TcpStream::connect(dst_addr)?;

        println!("conn from {} -> {}", src_addr, dst_addr);
        self.conns.insert((src.local_addr().expect("src local addr"), dst.local_addr().expect("dst local addr")), ForwardingConn::new(src, dst));
        Ok(())
    }
    pub fn run(&mut self) -> Result<()> {
        let mut to_remove = Vec::new();
        loop {
            let mut fds = vec![PollFd::new(self.stop_fd, EventFlags::POLLIN), PollFd::new(self.listener.as_raw_fd(), EventFlags::POLLIN | EventFlags::POLLPRI)];
            for conn in self.conns.values_mut() {
                conn.add_polls(&mut fds);
            }

            poll(&mut fds[..], -1)?;

            if !fds[0].revents().expect("stop_fd revents").is_empty() {
                println!("port {} forward shutting down", self.eport);
                break;
            }

            let mut i = 2;
            for conn in self.conns.values_mut() {
                match conn.update(fds[i], fds[i+1]) {
                    Ok(()) => {},
                    Err(e) => {
                        let addrs = conn.addrs().expect("connection addresses");
                        match e {
                            Error::ConnClosed => println!("conn closed {:?}", addrs),
                            e => eprintln!("forwarding error: {}", e),
                        }
                        to_remove.push(addrs);
                    },
                }
                i += 2;
            }
            if !fds[1].revents().expect("listening socket revents").is_empty() {
                match self.new_conn() {
                    Ok(_) => {},
                    Err(e) => eprintln!("error opening forwarding connection from {} -> {}: {}", self.eport, self.iport, e),
                }
            }
            fds.clear();

            if !to_remove.is_empty() {
                for addrs in to_remove.iter() {
                    self.conns.remove(addrs).expect("connection removal");
                }
                to_remove.clear();
            }
        }
        Ok(())
    }
}

struct Forwarding {
    stop_fd: RawFd,
    handle: thread::JoinHandle<Result<()>>,
}
impl Forwarding {
    pub fn new(eport: u16, user: &str, iport: u16) -> Result<Forwarding> {
        let stop_fd = eventfd(0, EfdFlags::empty()).expect("eventfd()");
        let mut inner = ForwardingInner::new(stop_fd, eport, user.to_owned(), iport)?;
        let handle = thread::spawn(move || inner.run());

        Ok(Forwarding {
            stop_fd,
            handle,
        })
    }

    pub fn stop(self) -> Result<()> {
        unistd::write(self.stop_fd, &1u64.to_ne_bytes())?;
        self.handle.join().expect("thread panicked")
    }
}

struct Proxy {
    ports: HashMap<u16, Forwarding>,
}
impl Proxy {
    pub fn new() -> Proxy {
        Proxy {
            ports: HashMap::new(),
        }
    }

    pub fn handle_command(&mut self, args: &[&str]) -> Result<()> {
        if args.is_empty() {
            return Err(Error::InvalidCommand("empty"));
        }

        match args[0] {
            "quit" => return Err(Error::Quit),
            "add" => {
                if args.len() != 4 {
                    return Err(Error::InvalidCommand("usage: add <external port> <user> <internal port>"));
                }

                let eport: u16 = args[1].parse()?;
                if self.ports.contains_key(&eport) {
                    return Err(Error::AlreadyForwarded(eport));
                }
                let iport: u16 = args[3].parse()?;

                self.ports.insert(eport, Forwarding::new(eport, args[2], iport)?);
            },
            "remove" => {
                if args.len() != 2 {
                    return Err(Error::InvalidCommand("usage: remove <external port>"));
                }

                let eport: u16 = args[1].parse()?;
                match self.ports.remove(&eport) {
                    Some(forwarding) => forwarding.stop()?,
                    None => return Err(Error::NotForwarded(eport)),
                }
            },
            _ => return Err(Error::InvalidCommand("unknown command")),
        }

        Ok(())
    }
    pub fn stop(self) -> Result<()> {
        for (_, forwarding) in self.ports {
            forwarding.stop()?;
        }
        Ok(())
    }
}

fn main() -> Result<()> {
    let mut sigmask = SigSet::empty();
    sigmask.add(Signal::SIGINT);
    sigmask.add(Signal::SIGTERM);
    sigmask.thread_set_mask()?;
    let quit_fd = SignalFd::new(&sigmask)?;

    let mut proxy = Proxy::new();
    let stdin = io::stdin();
    let mut fds = [PollFd::new(quit_fd.as_raw_fd(), EventFlags::POLLIN), PollFd::new(stdin.as_raw_fd(), EventFlags::POLLIN | EventFlags::POLLPRI)];
    loop {
        match poll(&mut fds, -1) {
            Ok(_) => {},
            Err(e) => return Err(e.into()),
        };
        if !fds[0].revents().expect("signalfd revents").is_empty() {
            println!("quitting");
            break;
        }

        let mut line = String::new();
        stdin.read_line(&mut line)?;
        let args: Vec<_> = line.trim().split(" ").collect();
        match proxy.handle_command(&args[..]) {
            Ok(_) => {},
            Err(Error::Quit) => break,
            Err(e) => eprintln!("{}", e),
        }
    }

    proxy.stop()?;
    Ok(())
}

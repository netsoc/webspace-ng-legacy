# Installation
1. Install [LXD](https://linuxcontainers.org/lxd/getting-started-cli/), via snap or otherwise
  - (Recommended) Create a network interface and enable NAT when asked in the setup process
2. Install [OpenResty](http://openresty.org/en/installation.html) 
  - It may be necessary to build from source as `webspace-ng` requires `ngx_stream_ssl_preread_module` (pass `--with-stream_ssl_preread_module` to `configure`)
3. Install Memcached
4. Clone this repo
5. Create a `webspace-admin` system group
  - Whatever user OpenResty runs under must be a member of this group
  - You should make `root` a member of this group
6. (Recommended) Create an LXD profile in order to set limits for user containers (CPU, memory, disk)
7. Install LuaExpat (usually via your system's package manager)
8. Install OpenResty packages (with the OpenResty Package Manager)
  - `opm get ledgetech/lua-resty-http`
  - `opm get bungle/lua-resty-template`
9. Build the Rust-based TCP proxy
  - `cd tcp-proxy/ && cargo build --release`
  - The resulting binary will be in `target/release/webspace-tcp-proxy`
  - Requires the 2018 edition of [Rust](https://www.rust-lang.org/learn/get-started)
10. Install `webspaced` and `webspace-cli`
  - `pip install .`

# Configuration
1. Run `webspaced` (as root) to generate an initial configuration file at `/etc/webspaced.yaml`
2. Edit `/etc/webspaced.yaml` as required
  - `bind_socket` is the path to the user-accessible Unix socket for interacting with the daemon (via `webspace-cli`)
  - `lxd.socket` is the location of LXD's interface socket
    - Usually `/var/lib/lxd/lxd.socket`
    - Under snap: `/var/snap/lxd/common/lxd/unix.socket`
  - `lxd.profile` is the LXD profile which new webspace containers will be based on
  - `lxd.suffix` is the suffix appended to each webspace's username for the container name
    - This should be unique among any other non-webspace LXD containers
  - `lxd.net.cidr` is the subnet of in which containers live (as configured when setting up LXD)
  - `lxd.net.container_iface` is the name of the network primary network interface in containers (usually `eth0`)
  - `domain_suffix` indicates the external hostname suffix - used for routing HTTP traffic in OpenResty
    - If the suffix was `.webspaces.com`, `http://root.webspaces.com` would route to `root`'s webspace
  - `max_startup_delay` is the maximum delay (in seconds) a user can have a connection hang when their container is not running
  - `run_limit` the maximum number of containers that can be running at once
    - The least-recently booted container will be shut down for a new one to boot
  - `ports.proxy_bin` is the path to the TCP proxy binary compiled earlier
  - `ports.start` and `ports.end` indicate the (inclusive) allowable port forwarding range
  - `ports.max` is the maximum number of ports a single user can forward
3. Install the provided systemd unit for `webspaced` and start / enable it
4. Set up an instance of `memcached` for OpenResty
  - It should be accessible _only_ to OpenResty over a Unix socket
  - For example: `memcached -u www-data -s /run/openresty-memcached/unix.socket`
5. Configure OpenResty for webspaces
  - (Recommended) Use `nginx/nginx.conf.sample` as a starting point for the main OpenResty configuration
  - Depending on your system and build of OpenResty, it may be necessary to add extra entries to `lua_package_path` and `lua_package_cpath` (in both the `stream` and `http` blocks) in order for OpenResty to find LuaExpat on your system
    - For example, on Debian Buster, it is necessary to add `/usr/lib/x86_64-linux-gnu/lua/5.1/?.so;` to `lua_package_cpath` and `/usr/share/lua/5.1/?.lua;` to `lua_package_path`
  - Replace instances of `/path/to/webspace-ng` with the path to this repo (should be readable by OpenResty)
  - Update the locations of the HTTPS, HTTPS error and HTTPS 502 sockets to your liking
    - **Any additional HTTPS server blocks should listen on the HTTPS socket - port 443 is used by the Lua code to determine which backend to route HTTPS traffic to by SNI**
6. Edit `nginx/constants.lua`
  - Update all of the required Unix sockets based on previously configured values (`webspaced`, OpenResty and Memcached)
  - Add any non-webspace hosts serving over HTTPS to the list
7. Profit!

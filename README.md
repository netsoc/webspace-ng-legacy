# webspace-ng
Next Generation webspaces powered by [LXD](https://linuxcontainers.org/).

## What does this do?
Allows users to have their own VM-like container to host a website on a shared IP (courtesy of LXD and [OpenResty](http://openresty.org) and some Python + Lua).

# For sysadmins
See [INSTALL.md](INSTALL.md).

# For users
## Getting started
`webspace-cli` is a command-line-based tool used to manage your webspace container.
1. Log into the server hosting `webspace-ng`-based webspaces (e.g. over SSH)
2. Run `webspace-cli images` to view a list of available Linux distributions to base your container off of
3. Do `webspace-cli init <your chosen image name / fingerprint>` to set up your container
4. `webspace-cli console` will attach you to the TTY of your container
    - Hit enter a few times and you should see a login prompt. The default login details will depend on your chosen image.
    - Press CTRL+] and then 'q' to detach from the console.
    - Note that it make take a few seconds to start your container before the console becomes ready.
5. From here you can use your container like a VM and install your webserver of choice
    - Make sure that your chosen webserver is configured to run at container startup - **your container could be shut down at any point to make room for others**
6. Try reaching your container in your browser!
    - You can check where your container is reachable by running `webspace-cli domains` - usually the default is something like `<username>.webhost.com`
    - SSL termination is enabled by default - `https://<username>.webhost.com` will use your hoster's SSL certificate and proxy to your plain HTTP server

_You can do `webspace-cli -h` and `webspace-cli <command> -h` for additional info._

## Boot / Shutdown policy
As mentioned above, your container can be shutdown automatically to make resources available for other users.

This shutdown policy is based on the order of startup - the longest running container will be shutdown first. If a request is made to your webspace is made but it is not running, it will be automatically started.
The browser will wait until startup is complete. Note that this wait is based on a fixed delay, you can set this via `webspace-cli config set startup_delay <seconds>`.

## SSL termination
By default, SSL for HTTPS requests to your webspace will be handled transparently by the hoster's reverse proxy - your container only needs to listen for HTTP requests.

However, you might want to roll your own SSL. If so, do `webspace-cli config set terminate_ssl false`. This will use some SNI magic to pass HTTPS requests directly through to your container. You'll need to get your own certificate (via Let's Encrypt or otherwise) and listen on a HTTPS port.

## HTTP(S) ports
By default, incoming requests will be proxied to port 80 in your container (port 443 for HTTPS with SSL termination disabled).

You can change these ports by doing `webspace-cli config set http_port <port>` and `webspace-cli config set https_port <port>` respectively.

## Custom domains
While your container will always be reachable by its default `<username>.webhost.com`, you might want to have a more user-friendly domain like `mywebsite.com`.

To set this up, you'll need to add `TXT` record in your domain registrar's DNS settings (to verify your ownership of the domain). The value of the record should look like this: `webspace:<username>` (without angle brackets).

You'll also need to add a `CNAME` or (`A `/` AAAA` record) pointing to your hoster's server so that requests will actually reach the webspace reverse proxy. **Note that `CNAME` records cannot be created for the root of your domain - you'll need to use an `A` / `AAAA` record instead.**

Wildcard domains (e.g. `*.mywebsite.com`) should also work.

**Note: If you want HTTPS to work correctly (no warning message in the browser), you'll need to disable SSL termination and obtain SSL certificates for your domain(s). SSL termination always uses your hoster's certificate which only works for the default domain.**

return {
	webspaced_sock = '/var/lib/webspace-ng/unix.socket',
	https_sock = 'unix:/var/run/openresty-https.sock',
	https_error_sock = 'unix:/var/run/openresty-https-error.sock',
	https_502_sock = 'unix:/var/run/openresty-https-502.sock',
	memcached_sock = 'unix:/tmp/memcached.sock',
	non_webspace_names = {
		["www.my.website"] = true,
		["my.website"] = true,
	},
}

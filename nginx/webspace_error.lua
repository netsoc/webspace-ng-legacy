local template = require('resty.template')

local messages = {
  memcached = 'Internal Memcached connection error',
  webspaced_request = 'Failed to connect to webspaced',
  webspaced_init = 'This user has not initialized their webspace!',
  webspaced_user = 'This user does not exist',
  webspaced_iface = 'Container network interface unavailable',
  webspaced_ip = 'Container is unreachable (no IP address)',
  ['502'] = 'Failed to connect to container over HTTP. Is there a server listening on port 80?',
  ssl_source = 'Failed to retrieve SSL source address from memcached',
  ssl_502 = 'Failed to connect to container over HTTPS (custom SSL cert). Is there a server listening on port 443?',
}

if messages[ngx.var.arg_type] then
  message = messages[ngx.var.arg_type]
else
  message = 'Unknown error'
end
ngx.status = 500
template.render('error.html', { message = message })

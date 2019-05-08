local balancer = require('ngx.balancer')
local constants = require('constants')

local state, status = balancer.get_last_failure()
if state == 'failed' then
  balancer.set_current_peer(constants.https_502_sock)
  return
end

local shared = ngx.shared.webspace
local peer, flags = shared:get('peer')
local unix, flags = shared:get('unix')
if unix then
  balancer.set_current_peer(peer)
else
  local tcp_port, flags = shared:get('tcp_port')
  balancer.set_current_peer(peer, tcp_port)
end

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
  balancer.set_current_peer(peer, 443)
end

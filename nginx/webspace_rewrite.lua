local rpc = require('unixrpc')
local json = require('json')
local memcached = require('resty.memcached')
local constants = require('constants')

local memc, err = memcached:new()
if not memc then
  ngx.log(ngx.ERR, 'failed to create memcached instance: ', err)
  return ngx.exec('/__webspace-error?type=memcached')
end
local ok, err = memc:connect(constants.memcached_sock)
if not ok then
  ngx.log(ngx.ERR, 'failed to connect memcached: ', err)
  return ngx.exec('/__webspace-error?type=memcached')
end

local function memc_close()
  local ok, err = memc:set_keepalive(10000, 100)
  if not ok then
    ngx.log(ngx.ERR, 'failed to set memcached keepalive: ', err)
    return ngx.exec('/__webspace-error?type=memcached')
  end
end

local res, err = rpc.call(constants.webspaced_sock, 'boot_and_host', ngx.var.user, false)
if not res then
  ngx.log(ngx.ERR, json.encode(err))
  memc_close()
  return ngx.exec('/__webspace-error?type=webspaced_request')
elseif res[1] == 'nil' then
  ngx.log(ngx.ERR, res[2])
  memc_close()
  return ngx.exec('/__webspace-error?type=webspaced_'..res[2])
else
  ngx.log(ngx.DEBUG, res[2])
  if ngx.var.https == 'on' then
    local ssl_source, flags, err = memc:get('ssl_source')
    if err then
      ngx.log(ngx.ERR, 'failed to retrieve value from memcached: ', err)
      memc_close()
      return ngx.exec('/__webspace-error?type=ssl_source')
    end
    ngx.var.real_source = ssl_source
  end
  ngx.var.target = res[2]
end

memc_close()

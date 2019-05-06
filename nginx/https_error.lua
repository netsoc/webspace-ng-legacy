local memcached = require('resty.memcached')
local constants = require('constants')

local function set_error(type)
  ngx.req.set_uri('/__webspace-error')
  ngx.req.set_uri_args({ type = type })
end

local memc, err = memcached:new()
if not memc then
  ngx.log(ngx.ERR, 'failed to create memcached instance: ', err)
  return set_error('memcached')
end
local ok, err = memc:connect(constants.memcached_sock)
if not ok then
  ngx.log(ngx.ERR, 'failed to connect memcached: ', err)
  return set_error('memcached')
end

local function memc_close()
  local ok, err = memc:set_keepalive(10000, 100)
  if not ok then
    ngx.log(ngx.ERR, 'failed to set memcached keepalive: ', err)
    return set_error('memcached')
  end
end

local type, flags, err = memc:get('error_type')
if not type and not err then
  memc_close()
  return set_error('unknown')
end
if err then
  memc_close()
  return set_error('memcached')
end
local ok, err = memc:delete('error_type')
if not ok then
  ngx.log(ngx.ERR, 'error deleting error type: '..err)
  memc_close()
  return set_error('memcached')
end

memc_close()
return set_error(type)

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

local function do_rewrite(webspace)
  ngx.log(ngx.DEBUG, 'webspace address: ', webspace)
  if ngx.var.https == 'on' then
    local ssl_source, flags, err = memc:get('ssl_source')
    if err then
      ngx.log(ngx.ERR, 'failed to retrieve value from memcached: ', err)
      memc_close()
      return ngx.exec('/__webspace-error?type=ssl_source')
    end
    ngx.var.real_source = ssl_source
  end
  ngx.var.target = webspace
  memc_close()
end
local function do_not_webspace()
  ngx.log(ngx.DEBUG, 'not a webspace: ', ngx.var.request_uri)
  memc_close()
  if ngx.var.uri == '/' then
    ngx.exec('/__non-webspace/index.html')
  else
    ngx.exec('/__non-webspace'..ngx.var.request_uri)
  end
end

local ssl_cached, flags, err = memc:get('webspace')
if err then
  ngx.log(ngx.ERR, 'failed to retrieve value from memcached: ', err)
  memc_close()
  return ngx.exec('/__webspace-error?type=ssl_source')
elseif ssl_cached then
  ngx.log(ngx.DEBUG, 'using cached webspace value from ssl preread')
  local ok, err = memc:delete('webspace')
  if not ok then
    ngx.log(ngx.ERR, 'failed to delete webspace value from memcached: ', err)
    memc_close()
    return ngx.exec('/__webspace-error?type=memcached')
  end

  if ssl_cached == 'not_webspace' then
    do_not_webspace()
  else
    do_rewrite(ssl_cached)
  end
else
  ngx.log(ngx.DEBUG, '_not_ using cached webspace value from ssl preread')
  local res, err = rpc.call(constants.webspaced_sock, 'boot_and_host', ngx.var.host, false)
  if not res then
    ngx.log(ngx.ERR, json.encode(err))
    memc_close()
    return ngx.exec('/__webspace-error?type=webspaced_request')
  elseif res[1] == 'nil' then
    if res[2] == 'not_webspace' then
      return do_not_webspace()
    end

    ngx.log(ngx.ERR, res[2])
    memc_close()
    return ngx.exec('/__webspace-error?type=webspaced_'..res[2])
  else
    do_rewrite(res[2]..':'..res[3])
  end
end

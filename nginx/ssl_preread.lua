local rpc = require('unixrpc')
local json = require('json')
local memcached = require('resty.memcached')
local constants = require('constants')

local shared = ngx.shared.webspace
shared:set('unix', true)

local memc, err = memcached:new()
if not memc then
  ngx.log(ngx.ERR, 'failed to create memcached instance: ', err)
  shared:set('peer', constants.https_error_sock)
  return
end
local ok, err = memc:connect(constants.memcached_sock)
if not ok then
  ngx.log(ngx.ERR, 'failed to connect memcached: ', err)
  shared:set('peer', constants.https_error_sock)
  return
end

local function memc_close()
  local ok, err = memc:set_keepalive(10000, 100)
  if not ok then
    ngx.log(ngx.ERR, 'failed to set memcached keepalive: ', err)
    shared:set('peer', constants.https_error_sock)
    return
  end
end

local server_name = ngx.var.ssl_preread_server_name
local res, err = rpc.call(constants.webspaced_sock, 'boot_and_host', server_name, true)
if not res then
  ngx.log(ngx.ERR, json.encode(err))
  shared:set('peer', constants.https_error_sock)
  memc:set('error_type', 'webspaced_request')
elseif res[1] == 'nil' then
  if res[2] == 'not_webspace' then
    ngx.log(ngx.DEBUG, 'not a webspace')
    shared:set('peer', constants.https_sock)

    if not constants.non_webspace_names[server_name] then
      ngx.log(ngx.DEBUG, 'will match default server, setting not_webspace')
      local ok, err = memc:set('webspace', 'not_webspace')
      if not ok then
        ngx.log(ngx.ERR, 'failed to set memcached value: ', err)
        shared:set('peer', constants.https_error_sock)
      end
    else
      ngx.log(ngx.DEBUG, 'will _not_ match default server, _not_ setting not_webspace')
    end
    return memc_close()
  end

  ngx.log(ngx.ERR, res[2])
  shared:set('peer', constants.https_error_sock)
  memc:set('error_type', 'webspaced_'..res[2])
else
  ngx.log(ngx.INFO, res[1]..'://'..res[2]..':'..res[3])
  if res[1] == 'https' then
    ngx.log(ngx.DEBUG, 'user wants their own ssl')
    shared:set('unix', false)
    shared:set('peer', res[2])
    shared:set('tcp_port', res[3])
  else
    ngx.log(ngx.DEBUG, 'doing ssl termination')
    shared:set('peer', constants.https_sock)

    local ok, err = memc:set('webspace', res[2]..':'..res[3])
    if not ok then
      ngx.log(ngx.ERR, 'failed to set memcached value: ', err)
      shared:set('peer', constants.https_error_sock)
      return memc_close()
    end
    local ok, err = memc:set('ssl_source', ngx.var.remote_addr)
    if not ok then
      ngx.log(ngx.ERR, 'failed to set memcached value: ', err)
      shared:set('peer', constants.https_error_sock)
      return memc_close()
    end
  end
end

memc_close()

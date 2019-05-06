-- Ripped from https://github.com/timn/lua-xmlrpc/blob/master/src/http.lua
-- Uses lua-resty-http for Unix socket support

local http   = require("resty.http")
local xmlrpc = require("xmlrpc")

module("unixrpc")

---------------------------------------------------------------------
-- Call a remote method.
-- @param socket String with the location of the Unix socket.
-- @param method String with the name of the method to be called.
-- @return Table with the response (could be a `fault' or a `params'
--	XML-RPC element).
---------------------------------------------------------------------
function call(socket, method, ...)
	local request_body = xmlrpc.clEncode(method, ...)

	local httpc = http.new()
	local c, err = httpc:connect('unix:' .. socket)
	if not c then
		return nil, err
	end

	local res, err = httpc:request({
		method = "POST",
		path = "/RPC2",
		body = request_body,
		headers = {
			["Host"] = socket,
			["User-agent"] = xmlrpc._PKGNAME .. " " .. xmlrpc._VERSION,
			["Content-type"] = "text/xml",
		}
	})

	if not res then
		httpc:close()
		return nil, err
	end

	if res.status ~= 200 or not res.has_body then
		httpc:close()
		return nil, res
	end

	local body, err = res:read_body()
	if not body then
		httpc:close()
		return nil, err
	end

	httpc:close()
	local ok, results = xmlrpc.clDecode(body)
	if not ok then
		return nil, results
	end
	return results
end

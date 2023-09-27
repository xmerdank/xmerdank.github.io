/*
CamScanner

***************************

Surge4 or Loon:

[Script]
http-response https:\/\/(api|api-cs)\.intsig\.net\/purchase\/cs\/query_property\? requires-body=1,max-size=0,script-path=https://xmerdank.github.io/xRocket/scripts/camscanner.js

[MITM]
hostname = ap*.intsig.net

**************************/
let obj = JSON.parse($response.body);
obj = {"data":{"psnl_vip_property":{"expiry":"2013017600"}}};
$done({body: JSON.stringify(obj)});
/*
Polarr

***************************
QuantumultX:

[rewrite_local]
^https:\/\/api\.polaxiong\.com\/v1\/payments\/appleiap\/receipts\/confirmation url script-response-body https://xmerdank.github.io/xRocket/scripts/
polarr.js

[mitm]
hostname = api.polaxiong.com

***************************
Surge4 or Loon:

[Script]
http-response ^https:\/\/api\.polaxiong\.com\/v1\/payments\/appleiap\/receipts\/confirmation requires-body=1,max-size=0,script-path=https://xmerdank.github.io/xRocket/scripts/
polarr.js

[MITM]
hostname = api.polaxiong.com

**************************/

const sta = typeof $task !== "undefined" ? "HTTP/1.1 200 OK" : 200;
const res = $response;
const req = $request;

if (res.body && req.method == "PUT") {
  $done({
    body: JSON.stringify({
      "app": "PPE",
      "isUnlimited": true,
      "membershipExpiryDate": "2028-06-06T08:00:00.000Z"
    }),
    status: sta,
    headers: res.headers
  });
} else {
  $done({});
}

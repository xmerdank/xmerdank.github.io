/*
PicsArt
***************************
Surge4 or Loon:

[Script]
http-response https:\/\/api\.(picsart|meiease)\.c(n|om)\/users\/show\/me\.json requires-body=1,max-size=0,script-path=https://xmerdank.github.io/xRocket/scripts/picsart.js

[MITM]
hostname = api.picsart.c*, api.meiease.c*

**************************/

let obj = JSON.parse($response.body);
obj.subscription.granted = "true";
$done({body: JSON.stringify(obj)});

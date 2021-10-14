/*
WPS Office
^https?:\/\/account\.wps\.cn\/api\/users requires-body=1,max-size=-1
hostname = account.wps.cn

*/

var body = JSON.parse($response.body);
var obj = {
  exp: 0,
  level: 3,
  privilege: [
    { spid: "data_recover", times: 0, expire_time: 1846256142 },
    { spid: "ocr", times: 0, expire_time: 1846256142 },
    { spid: "pdf2doc", times: 0, expire_time: 1846256142 },
    { spid: "pdf_merge", times: 0, expire_time: 1846256142 },
    { spid: "pdf_sign", times: 0, expire_time: 1846256142 },
    { spid: "pdf_split", times: 0, expire_time: 1846256142 }
  ],
  result: "ok",
  total_buy: 0,
  total_cost: -30,
  userid: body.userid,
  vip: {
    name: "Super member",
    has_ad: 0,
    memberid: 40,
    expire_time: 1846256142,
    enabled: [
      { memberid: 40, name: "Super member", expire_time: 1846256142 },
      { memberid: 20, name: "WPS member", expire_time: 1846256142 },
      { memberid: 12, name: "Rice husk member", expire_time: 1846256142 }
    ]
  },
  wealth: 0,
  expire_time: 1846256142
};

$done({ body: JSON.stringify(obj) });

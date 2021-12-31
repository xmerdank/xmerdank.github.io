var obj = JSON.parse($response.body);

obj={
  "purchased" : "true"
}

$done({body: JSON.stringify(obj)});

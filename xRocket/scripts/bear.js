/*
^https:\/\/buy\.itunes\.apple\.com\/verifyReceipt url script-response-body JS/bear.js
buy.itunes.apple.com
*/

var obj = JSON.parse($response.body);
var bundle_id = obj.receipt["bundle_id"];
if (bundle_id == "net.shinyfrog.bear-iOS") {
  obj = {
    status: 0,
    environment: "Production",
    receipt: {
      receipt_type: "Production",
      adam_id: 1016366447,
      app_item_id: 1016366447,
      bundle_id: "net.shinyfrog.bear-iOS",
      application_version: "7133",
      download_id: 92018757521008,
      version_external_identifier: 831147846,
      receipt_creation_date: "2019-08-10 23:17:58 Etc/GMT",
      receipt_creation_date_ms: "1565479078000",
      receipt_creation_date_pst: "2019-08-10 16:17:58 America/Los_Angeles",
      request_date: "2019-08-10 23:18:04 Etc/GMT",
      request_date_ms: "1565479084140",
      request_date_pst: "2019-08-10 16:18:04 America/Los_Angeles",
      original_purchase_date: "2016-11-05 07:20:24 Etc/GMT",
      original_purchase_date_ms: "1478330424000",
      original_purchase_date_pst: "2016-11-05 00:20:24 America/Los_Angeles",
      original_application_version: "3562",
      in_app: [
        {
          quantity: "1",
          product_id: "net.shinyfrog.bear_iOS.pro_yearly_subscription_bis",
          transaction_id: "520000469131745",
          original_transaction_id: "520000469131745",
          purchase_date: "2019-08-10 23:17:57 Etc/GMT",
          purchase_date_ms: "1565479077000",
          purchase_date_pst: "2019-08-10 16:17:57 America/Los_Angeles",
          original_purchase_date: "2019-08-10 23:17:57 Etc/GMT",
          original_purchase_date_ms: "1565479077000",
          original_purchase_date_pst: "2019-08-10 16:17:57 America/Los_Angeles",
          expires_date: "2099-09-10 23:17:57 Etc/GMT",
          expires_date_ms: "4092736677000",
          expires_date_pst: "2099-09-10 16:17:57 America/Los_Angeles",
          web_order_line_item_id: "520000150747696",
          is_trial_period: "true",
          is_in_intro_offer_period: "false"
        }
      ]
    },
    latest_receipt_info: [
      {
        quantity: "1",
        product_id: "net.shinyfrog.bear_iOS.pro_yearly_subscription_bis",
        transaction_id: "520000469131745",
        original_transaction_id: "520000469131745",
        purchase_date: "2019-08-10 23:17:57 Etc/GMT",
        purchase_date_ms: "1565479077000",
        purchase_date_pst: "2019-08-10 16:17:57 America/Los_Angeles",
        original_purchase_date: "2019-08-10 23:17:57 Etc/GMT",
        original_purchase_date_ms: "1565479077000",
        original_purchase_date_pst: "2019-08-10 16:17:57 America/Los_Angeles",
        expires_date: "2099-09-10 23:17:57 Etc/GMT",
        expires_date_ms: "4092736677000",
        expires_date_pst: "2099-09-10 16:17:57 America/Los_Angeles",
        web_order_line_item_id: "520000150747696",
        is_trial_period: "true",
        is_in_intro_offer_period: "false"
      }
    ],
    latest_receipt:
      "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",
    pending_renewal_info: [
      {
        auto_renew_product_id:
          "net.shinyfrog.bear_iOS.pro_yearly_subscription_bis",
        original_transaction_id: "520000469131745",
        product_id: "net.shinyfrog.bear_iOS.pro_yearly_subscription_bis",
        auto_renew_status: "1"
      }
    ]
  };
}
$done({body:JSON.stringify(obj)});

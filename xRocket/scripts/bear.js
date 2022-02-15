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
package policy

deny[msg] {
  some rc
  rc := input.resource_changes[_]
  rc.type == "azurerm_storage_account"
  not rc.change.after.enable_https_traffic_only
  msg := {
    "msg": "Storage account must enforce HTTPS-only traffic",
    "resource": rc.address,
    "severity": "high"
  }
}

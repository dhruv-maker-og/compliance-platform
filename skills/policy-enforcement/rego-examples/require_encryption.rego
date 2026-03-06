# METADATA
# title: Require encryption at rest for storage accounts
# description: All Azure storage accounts must have infrastructure encryption and HTTPS-only enabled
# severity: high
# author: compliance-agent
# framework: PCI-DSS
# controls: ["3.5"]

package policy.storage.encryption

import rego.v1

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_storage_account"
	not resource.values.enable_https_traffic_only
	msg := sprintf(
		"Storage account '%s' must enforce HTTPS-only traffic [PCI-DSS 3.5, 4.1]",
		[resource.name],
	)
}

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_storage_account"
	not resource.values.infrastructure_encryption_enabled
	msg := sprintf(
		"Storage account '%s' must have infrastructure encryption enabled [PCI-DSS 3.5]",
		[resource.name],
	)
}

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_storage_account"
	resource.values.min_tls_version != "TLS1_2"
	msg := sprintf(
		"Storage account '%s' must use TLS 1.2 or higher (current: %s) [PCI-DSS 4.1]",
		[resource.name, resource.values.min_tls_version],
	)
}

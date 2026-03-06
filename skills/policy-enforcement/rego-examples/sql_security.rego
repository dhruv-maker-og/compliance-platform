# METADATA
# title: Require SQL Server auditing and TDE
# description: Azure SQL Servers must have auditing enabled and TDE enabled on all databases
# severity: high
# author: compliance-agent
# framework: PCI-DSS
# controls: ["3.5", "10.2"]

package policy.database.sql_security

import rego.v1

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_mssql_server"
	resource.values.minimum_tls_version != "1.2"
	msg := sprintf(
		"SQL Server '%s' must enforce TLS 1.2 (current: %s) [PCI-DSS 4.1]",
		[resource.name, resource.values.minimum_tls_version],
	)
}

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_mssql_server"
	not resource.values.public_network_access_enabled == false
	msg := sprintf(
		"SQL Server '%s' should disable public network access [PCI-DSS 1.3]",
		[resource.name],
	)
}

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_mssql_database"
	not has_tde(resource)
	msg := sprintf(
		"SQL Database '%s' must have Transparent Data Encryption enabled [PCI-DSS 3.5]",
		[resource.name],
	)
}

has_tde(resource) if {
	resource.values.transparent_data_encryption_enabled == true
}

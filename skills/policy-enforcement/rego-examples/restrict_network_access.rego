# METADATA
# title: Restrict network access — no public ingress on sensitive ports
# description: NSG rules must not allow unrestricted inbound access from 0.0.0.0/0 on sensitive ports
# severity: high
# author: compliance-agent
# framework: PCI-DSS
# controls: ["1.2", "1.3"]

package policy.network.restrict_public_access

import rego.v1

sensitive_ports := {22, 3389, 1433, 3306, 5432, 27017}

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_network_security_rule"
	resource.values.direction == "Inbound"
	resource.values.access == "Allow"
	resource.values.source_address_prefix == "*"
	port := to_number(resource.values.destination_port_range)
	port in sensitive_ports
	msg := sprintf(
		"NSG rule '%s' allows unrestricted inbound access on port %d [PCI-DSS 1.2, 1.3]",
		[resource.name, port],
	)
}

deny contains msg if {
	resource := input.planned_values.root_module.resources[_]
	resource.type == "azurerm_network_security_rule"
	resource.values.direction == "Inbound"
	resource.values.access == "Allow"
	resource.values.source_address_prefix == "0.0.0.0/0"
	port := to_number(resource.values.destination_port_range)
	port in sensitive_ports
	msg := sprintf(
		"NSG rule '%s' allows 0.0.0.0/0 inbound on port %d [PCI-DSS 1.2, 1.3]",
		[resource.name, port],
	)
}

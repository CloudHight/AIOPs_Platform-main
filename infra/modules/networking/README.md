# networking

Reserved module for future VPC, subnet, route table, and VPC endpoint extraction.

The current workload module uses the account default VPC discovery path for a compact demo deployment. A production expansion should move VPC/subnet/security-group ownership here and pass subnet and security group IDs into workload and endpoint modules.

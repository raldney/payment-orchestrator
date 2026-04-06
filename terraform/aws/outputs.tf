output "instance_public_ip" {
  description = "IP Público da instância EC2"
  value       = aws_instance.app_server.public_ip
}

output "instance_public_dns" {
  description = "DNS Público da instância EC2"
  value       = aws_instance.app_server.public_dns
}

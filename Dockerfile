FROM odoo:latest

# Set environment variable to include enterprise addons
ENV ODOO_ADDONS_PATH=/mnt/enterprise-addons 

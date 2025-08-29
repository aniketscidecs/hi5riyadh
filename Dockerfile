FROM odoo:latest

# Set environment variable to include enterprise addons
ENV ODOO_ADDONS_PATH=/mnt/enterprise-addons 

# Install Python dependencies for Kids Club module
USER root
RUN pip3 install --break-system-packages python-barcode Pillow

# Switch back to odoo user
USER odoo

# install requirement.txt


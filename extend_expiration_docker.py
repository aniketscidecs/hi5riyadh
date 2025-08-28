#!/usr/bin/env python3
import psycopg2
from datetime import datetime, timedelta

# Database connection parameters for Docker
DB_HOST = "db"  # Docker service name
DB_PORT = "5432"
DB_NAME = "odoo"
DB_USER = "odoo"
DB_PASSWORD = "odoo"

def extend_database_expiration():
    try:
        # Connect to the database
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
        
        cursor = conn.cursor()
        
        # Set expiration date to 1 year from now
        new_expiration_date = (datetime.now() + timedelta(days=365)).strftime('%Y-%m-%d')
        
        # Update the expiration date parameter
        cursor.execute("""
            UPDATE ir_config_parameter 
            SET value = %s 
            WHERE key = 'database.expiration_date'
        """, (new_expiration_date,))
        
        # If the parameter doesn't exist, create it
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO ir_config_parameter (key, value, create_date, write_date)
                VALUES ('database.expiration_date', %s, NOW(), NOW())
            """, (new_expiration_date,))
        
        conn.commit()
        print(f"✅ Database expiration extended to: {new_expiration_date}")
        
        # Verify the change
        cursor.execute("SELECT value FROM ir_config_parameter WHERE key = 'database.expiration_date'")
        result = cursor.fetchone()
        if result:
            print(f"✅ Verified expiration date: {result[0]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    extend_database_expiration() 

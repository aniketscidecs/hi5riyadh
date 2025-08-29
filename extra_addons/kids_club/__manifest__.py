{
    'name': 'Kids Club',
    'version': '1.0.0',
    'category': 'Entertainment',
    'summary': 'Kids Club Management for Hi5 Entertainment Centre',
    'description': """
        Kids Club Management Module
        ===========================
        
        This module provides comprehensive management features for Hi5 Entertainment Centre's Kids Club:
        
        * Member registration and management
        * Activity scheduling and tracking
        * Subscription package management
        * Parent communication tools
        * Safety and attendance monitoring
    """,
    'author': 'Hi5 Entertainment Centre',
    'website': 'https://hi5riyadh.com',
    'depends': ['base', 'mail', 'contacts'],
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'views/subscription_package_views.xml',
        'views/child_views.xml',
        'views/customer_views.xml',
        'views/kids_club_menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,  # This makes it appear as a main app
    'auto_install': False,
    'license': 'LGPL-3',
}

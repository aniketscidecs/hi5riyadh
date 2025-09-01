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
    'depends': ['base', 'mail', 'contacts', 'sale', 'account'],
    'assets': {
        'web.assets_backend': [
            'kids_club/static/src/css/kids_dashboard.css',
            'kids_club/static/src/js/kids_dashboard.js',
        ],
    },
    'version': '1.0.1',  # Force asset reload
    'data': [
        'security/ir.model.access.csv',
        'data/sequences.xml',
        'data/subscription_sequences.xml',
        'data/checkin_data.xml',
        'views/subscription_package_views.xml',
        'views/child_views.xml',
        'views/checkin_views.xml',
        'views/checkout_wizard_views.xml',
        'views/customer_views.xml',
        'views/kids_club_menus.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,  # This makes it appear as a main app
    'auto_install': False,
    'license': 'LGPL-3',
}

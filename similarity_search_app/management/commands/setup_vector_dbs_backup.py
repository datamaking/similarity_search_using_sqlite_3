import os
import sqlite3
import json
from django.core.management.base import BaseCommand
from django.conf import settings
from sentence_transformers import SentenceTransformer


class Command(BaseCommand):
    help = 'Setup vector databases and populate with sample data'

    def __init__(self):
        super().__init__()
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    def handle(self, *args, **options):
        # Create vector_dbs directory if it doesn't exist
        vector_db_dir = settings.BASE_DIR / 'vector_dbs'
        os.makedirs(vector_db_dir, exist_ok=True)

        # Setup databases for each source type
        source_types = ['ADMIN', 'IT', 'FINANCE', 'HR']

        for source_type in source_types:
            self.stdout.write(f'Setting up {source_type} database...')
            self.setup_database(source_type)
            self.stdout.write(f'Populating {source_type} database with sample data...')
            self.populate_sample_data(source_type)
            self.stdout.write(self.style.SUCCESS(f'{source_type} database setup complete!'))

    def setup_database(self, source_type):
        """Create database tables for a source type"""
        db_path = settings.VECTOR_DATABASES[source_type]
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Create source table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS source_tbl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_text TEXT NOT NULL,
                category TEXT,
                created_date TEXT,
                author TEXT,
                department TEXT,
                priority TEXT,
                status TEXT
            )
        ''')

        # Create embedding table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS embedding_tbl (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER,
                embedding_vect TEXT,
                metadata TEXT,
                FOREIGN KEY (source_id) REFERENCES source_tbl (id)
            )
        ''')

        # Try to load sqlite-vec extension and create vector index
        try:
            conn.enable_load_extension(True)
            conn.load_extension("vec0")

            # Create vector index if sqlite-vec is available
            cursor.execute('''
                CREATE VIRTUAL TABLE IF NOT EXISTS vec_index USING vec0(
                    embedding_vect float[384]
                )
            ''')
            self.stdout.write(f'sqlite-vec extension loaded for {source_type}')
        except:
            self.stdout.write(f'sqlite-vec extension not available for {source_type}, using fallback')

        conn.commit()
        conn.close()

    def populate_sample_data(self, source_type):
        """Populate database with sample data"""
        db_path = settings.VECTOR_DATABASES[source_type]
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Generate sample data based on source type
        sample_data = self.generate_sample_data(source_type)

        # Batch insert for better performance
        batch_size = 100
        for i in range(0, len(sample_data), batch_size):
            batch = sample_data[i:i + batch_size]

            # Insert source records
            source_records = []
            for item in batch:
                source_records.append((
                    item['source_text'],
                    item['category'],
                    item['created_date'],
                    item['author'],
                    item['department'],
                    item['priority'],
                    item['status']
                ))

            cursor.executemany('''
                INSERT INTO source_tbl (source_text, category, created_date, author, department, priority, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', source_records)

            # Get the inserted IDs
            start_id = cursor.lastrowid - len(batch) + 1

            # Generate embeddings and insert
            embedding_records = []
            for idx, item in enumerate(batch):
                source_id = start_id + idx
                embedding = self.model.encode(item['source_text'])
                metadata = {
                    'category': item['category'],
                    'department': item['department'],
                    'priority': item['priority']
                }

                embedding_records.append((
                    source_id,
                    json.dumps(embedding.tolist()),
                    json.dumps(metadata)
                ))

            cursor.executemany('''
                INSERT INTO embedding_tbl (source_id, embedding_vect, metadata)
                VALUES (?, ?, ?)
            ''', embedding_records)

            conn.commit()
            self.stdout.write(f'Inserted batch {i // batch_size + 1} for {source_type}')

        conn.close()

    def generate_sample_data(self, source_type):
        """Generate sample data for each source type"""
        import random
        from datetime import datetime, timedelta

        base_data = {
            'ADMIN': [
                "Company policy update regarding remote work procedures",
                "New employee onboarding checklist and requirements",
                "Office security protocols and access card management",
                "Meeting room booking system guidelines",
                "Corporate communication standards and email etiquette",
                "Expense reporting procedures and approval workflow",
                "Document management system usage instructions",
                "Visitor management and registration process",
                "Emergency evacuation procedures and safety protocols",
                "Equipment procurement and asset management guidelines"
            ],
            'IT': [
                "Network security best practices and password policies",
                "Software installation and license management procedures",
                "Database backup and recovery protocols",
                "System monitoring and performance optimization",
                "Cybersecurity incident response procedures",
                "Cloud infrastructure management guidelines",
                "API documentation and integration standards",
                "Code review and deployment procedures",
                "Server maintenance and update schedules",
                "Help desk ticketing system workflow"
            ],
            'FINANCE': [
                "Budget planning and allocation procedures",
                "Invoice processing and payment authorization",
                "Financial reporting and compliance requirements",
                "Audit preparation and documentation standards",
                "Cost center management and tracking",
                "Revenue recognition and accounting principles",
                "Tax filing and regulatory compliance procedures",
                "Cash flow management and forecasting",
                "Vendor payment terms and contract management",
                "Financial risk assessment and mitigation strategies"
            ],
            'HR': [
                "Employee performance review and evaluation process",
                "Recruitment and hiring procedures",
                "Benefits enrollment and administration",
                "Training and development program guidelines",
                "Disciplinary action and grievance procedures",
                "Leave management and time-off policies",
                "Compensation and salary review process",
                "Employee engagement and satisfaction surveys",
                "Workplace diversity and inclusion initiatives",
                "Exit interview and offboarding procedures"
            ]
        }

        categories = {
            'ADMIN': ['Policy', 'Procedure', 'Guidelines', 'Standards'],
            'IT': ['Security', 'Development', 'Infrastructure', 'Support'],
            'FINANCE': ['Accounting', 'Compliance', 'Planning', 'Reporting'],
            'HR': ['Recruitment', 'Performance', 'Benefits', 'Training']
        }

        authors = [
            'John Smith', 'Sarah Johnson', 'Michael Brown', 'Emily Davis',
            'David Wilson', 'Lisa Anderson', 'Robert Taylor', 'Jennifer Martinez'
        ]

        priorities = ['High', 'Medium', 'Low']
        statuses = ['Active', 'Draft', 'Under Review', 'Archived']

        sample_data = []
        base_texts = base_data[source_type]

        # Generate 1000+ records by expanding base data
        for i in range(1000):
            base_text = random.choice(base_texts)

            # Add variations to create unique content
            variations = [
                f"Updated {base_text.lower()} for Q{random.randint(1, 4)} {random.randint(2020, 2024)}",
                f"Revised {base_text.lower()} including new compliance requirements",
                f"Enhanced {base_text.lower()} with additional security measures",
                f"Streamlined {base_text.lower()} for improved efficiency",
                f"Comprehensive guide for {base_text.lower()}",
                base_text,
                f"Best practices for {base_text.lower()}",
                f"Step-by-step instructions for {base_text.lower()}",
                f"Advanced techniques for {base_text.lower()}",
                f"Troubleshooting guide for {base_text.lower()}"
            ]

            source_text = random.choice(variations)

            # Generate random date within last 2 years
            start_date = datetime.now() - timedelta(days=730)
            random_date = start_date + timedelta(days=random.randint(0, 730))

            sample_data.append({
                'source_text': source_text,
                'category': random.choice(categories[source_type]),
                'created_date': random_date.strftime('%Y-%m-%d'),
                'author': random.choice(authors),
                'department': source_type,
                'priority': random.choice(priorities),
                'status': random.choice(statuses)
            })

        return sample_data
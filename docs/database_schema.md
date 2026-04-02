# FlynJet Database Schema

## Overview
FlynJet uses PostgreSQL as its primary database with Redis for caching and queues.

## Core Tables

### accounts_user
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| email | VARCHAR | User email (unique) |
| password | VARCHAR | Hashed password |
| first_name | VARCHAR | First name |
| last_name | VARCHAR | Last name |
| user_type | VARCHAR | user/agent/admin |
| is_active | BOOLEAN | Account active status |
| date_joined | TIMESTAMP | Account creation date |

### accounts_userprofile
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| user_id | UUID | Foreign key to accounts_user |
| profile_image | VARCHAR | Profile picture path |
| nationality | VARCHAR | Nationality |
| passport_number | VARCHAR | Passport number |
| emergency_contact | VARCHAR | Emergency contact |

### fleet_aircraft
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| registration_number | VARCHAR | Aircraft registration |
| manufacturer_id | UUID | Foreign key to fleet_manufacturer |
| category_id | UUID | Foreign key to fleet_category |
| model | VARCHAR | Aircraft model |
| passenger_capacity | INTEGER | Max passengers |
| max_range_nm | INTEGER | Range in nautical miles |
| hourly_rate_usd | DECIMAL | Hourly rental rate |
| status | VARCHAR | available/maintenance/etc |

### bookings_booking
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| booking_reference | VARCHAR | Unique booking code |
| user_id | UUID | Foreign key to accounts_user |
| aircraft_id | UUID | Foreign key to fleet_aircraft |
| departure_airport | VARCHAR | IATA code |
| arrival_airport | VARCHAR | IATA code |
| departure_datetime | TIMESTAMP | Flight departure |
| status | VARCHAR | Booking status |
| total_amount_usd | DECIMAL | Total price |

### payments_payment
| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| transaction_id | VARCHAR | Unique transaction ID |
| user_id | UUID | Foreign key to accounts_user |
| booking_id | UUID | Foreign key to bookings_booking |
| amount_usd | DECIMAL | Payment amount |
| payment_method | VARCHAR | visa/crypto/etc |
| status | VARCHAR | Payment status |
| payment_date | TIMESTAMP | When paid |

## Relationships

- User → Profile (One-to-One)
- User → Bookings (One-to-Many)
- Booking → Aircraft (Many-to-One)
- Booking → Payment (One-to-Many)
- Aircraft → Category (Many-to-One)
- Aircraft → Manufacturer (Many-to-One)

## Indexes

- accounts_user: email, user_type
- fleet_aircraft: status, category_id
- bookings_booking: booking_reference, user_id, departure_datetime
- payments_payment: transaction_id, user_id, status

## Partitioning

Large tables (bookings_booking, payments_payment) are partitioned by date for better performance.

## Caching Strategy

- Session data: Redis
- API responses: Redis with TTL
- Frequently accessed queries: Redis
- Rate limiting: Redis

## Backup Strategy

- Daily full backups
- Hourly WAL archiving
- 30-day retention
- Off-site replication
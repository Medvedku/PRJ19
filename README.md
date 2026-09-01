# PRJ-19 Data Pipeline & Analytics

Automated ingestion, storage, and analytical setup for the **PRJ-19** collection dataset.

---

## Prerequisites & Secrets Setup

This project relies on environment variables for database credentials and remote access. Key operational scripts will fail if these variables are missing.

### 1. Environment File (`.env`)

Create a `.env` file in the root directory of the project:

```bash
cp .env.example .env  # or create .env manually
```
Add your credentials inside `.env`:

```
MONGODB_URI="mongodb+srv://<username>:<password>@cluster.mongodb.net/?retryWrites=true&w=majority"
DUCKDB_PASSWORD="your_secure_password_here"
```
> **Note:** Never commit the .env file to git. It is excluded via .gitignore.
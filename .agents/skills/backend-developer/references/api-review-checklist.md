# Backend API review checklist

Use this checklist when it applies; adapt it to the repository rather than treating it as a rigid template.

## API contract
- Is the HTTP method appropriate for the operation?
- Are path and query parameters validated?
- Are success and error response shapes consistent?
- Are status codes meaningful (for example 200, 201, 204, 400, 401, 403, 404, 409, 422, 500)?
- Is pagination needed for collection endpoints?

## Flask structure
- Are routes grouped into appropriately named Blueprints?
- Is each Blueprint registered once in the application factory or entry point?
- Are route handlers small enough to understand and test?
- Is business logic placed consistently with the existing project?

## Database
- Are relationships and foreign keys correct?
- Are nullability and uniqueness constraints appropriate?
- Is a migration required?
- Has the migration been reviewed before execution?
- Are destructive changes avoided unless explicitly approved?

## Security
- Are passwords hashed with an established password-hashing library?
- Are protected endpoints authenticated and authorized?
- Are secrets stored in environment configuration?
- Is sensitive information excluded from responses and logs?
- Are database queries parameterized or performed through the ORM?

## Tests and docs
- Are happy paths and failure paths covered?
- Are authorization and validation cases covered?
- Does Swagger/OpenAPI match the actual implementation?
- Were tests actually executed, and are results reported accurately?

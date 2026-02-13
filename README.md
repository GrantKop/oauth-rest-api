# OAuth REST API

This project is a REST API that uses OAuth-based authentication (via Auth0) to control access to protected resources. It exposes endpoints for managing application data (such as users and courses) and enforces authorization rules so only properly authenticated clients can perform restricted actions.

The API works by validating incoming requests using JSON Web Tokens (JWTs) issued by Auth0. Clients authenticate with Auth0 to obtain an access token, then include that token with API requests. The server verifies the token’s signature and claims before allowing access to protected routes, and uses Google Cloud services for hosting/configuration and for storing application data.

This was an assignment for CS 493 at Oregon State University.

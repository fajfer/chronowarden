# Chronowarden Frontend

<!--
SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

Svelte-based web interface for Chronowarden secret management service.

## Features

- Dashboard showing API and Vault connection status
- Secret management interface
- HashiCorp Vault connection configuration
- Responsive design with light/dark mode support

## Development

### Prerequisites

- Node.js 18+
- npm

### Installation

```bash
npm install
```

### Running the development server

```bash
npm run dev
```

Then open http://localhost:5173 in your browser.

### Building for production

```bash
npm run build
```

Build output will be in the `dist` directory.

### Type checking

```bash
npm run check
```

## Configuration

Set the backend API URL via the `VITE_API_URL` environment variable:

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

## Components

- `ApiStatus` - Shows backend API connection status
- `VaultStatus` - HashiCorp Vault connection management
- `SecretsList` - List and manage secrets
- `Card` - Reusable card component

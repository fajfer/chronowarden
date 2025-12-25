<!--
SPDX-FileCopyrightText: 2025 Damian Fajfer <damian@fajfer.org>

SPDX-License-Identifier: EUPL-1.2
-->

<script lang="ts">
  import { ApiStatus, VaultStatus, SecretsList } from './lib/components';
</script>

<main>
  <header>
    <h1>🔐 Chronowarden</h1>
    <p class="tagline">Secret Management Service</p>
  </header>

  <div class="dashboard">
    <section class="sidebar">
      <ApiStatus />
      <VaultStatus />
    </section>

    <section class="content">
      <SecretsList />
    </section>
  </div>
</main>

<style>
  main {
    max-width: 1400px;
    margin: 0 auto;
    padding: 2rem;
  }

  header {
    text-align: center;
    margin-bottom: 2rem;
  }

  header h1 {
    font-size: 2.5rem;
    margin: 0;
    color: var(--heading-color, #fff);
  }

  .tagline {
    color: var(--text-muted, #999);
    margin: 0.5rem 0 0 0;
  }

  .dashboard {
    display: grid;
    grid-template-columns: 350px 1fr;
    gap: 2rem;
  }

  .sidebar {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .content {
    min-width: 0;
  }

  @media (max-width: 900px) {
    .dashboard {
      grid-template-columns: 1fr;
    }
  }
</style>

<script setup lang="ts">
defineProps<{
  eyebrow?: string
  title: string
  description?: string
  compactActions?: boolean
}>()
</script>

<template>
  <article class="summary-card">
    <div class="summary-header">
      <div class="summary-copy">
        <p v-if="eyebrow" class="summary-eyebrow">{{ eyebrow }}</p>
        <h3 class="summary-title">{{ title }}</h3>
        <p v-if="description" class="summary-description">{{ description }}</p>
      </div>
      <div v-if="$slots.actions" class="summary-actions" :class="{ compact: compactActions }">
        <slot name="actions" />
      </div>
    </div>

    <div v-if="$slots.meta" class="summary-meta">
      <slot name="meta" />
    </div>

    <div v-if="$slots.default" class="summary-body">
      <slot />
    </div>
  </article>
</template>

<style scoped>
.summary-card {
  border-radius: 30px;
  border: 1px solid rgba(221, 228, 242, 0.92);
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.9), rgba(249, 251, 255, 0.96));
  box-shadow: 0 22px 48px rgba(97, 107, 143, 0.08);
  padding: 24px;
}

.summary-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.summary-copy {
  min-width: 0;
}

.summary-eyebrow {
  margin: 0 0 12px;
  color: #8e99b1;
  font-size: 12px;
  font-weight: 800;
  letter-spacing: 0.18em;
  text-transform: uppercase;
}

.summary-title {
  margin: 0;
  color: #15203a;
  font-size: 20px;
  line-height: 1.25;
  word-break: break-word;
}

.summary-description {
  margin: 10px 0 0;
  color: #8390ab;
  font-size: 14px;
  line-height: 1.8;
}

.summary-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  gap: 10px;
}

.summary-actions.compact {
  gap: 8px;
}

.summary-meta {
  display: grid;
  gap: 12px;
  margin-top: 18px;
}

.summary-body {
  margin-top: 18px;
}

@media (max-width: 760px) {
  .summary-header {
    flex-direction: column;
  }

  .summary-actions {
    justify-content: flex-start;
  }
}
</style>

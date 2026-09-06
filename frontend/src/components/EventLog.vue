<template>
  <div class="event-log">
    <div class="log-header">
      <span class="log-icon">📋</span>
      <h2 class="log-title">Log de Eventos</h2>
      <span class="log-count">{{ events.length }}</span>
    </div>

    <TransitionGroup name="event-list" tag="ul" class="log-list">
      <li
        v-for="ev in events"
        :key="ev.time + ev.player"
        class="log-item"
        :class="`event-${ev.event_type}`"
      >
        <span class="event-badge">{{ eventEmoji(ev.event_type) }}</span>
        <div class="event-info">
          <span class="event-type">{{ ev.event_type.toUpperCase() }}</span>
          <span class="event-player">Jogador {{ ev.player }}</span>
        </div>
        <span class="event-time">{{ formatTime(ev.time) }}</span>
      </li>
    </TransitionGroup>

    <p v-if="events.length === 0" class="log-empty">
      Nenhum evento na última hora. Pressione o botão na quadra!
    </p>
  </div>
</template>

<script setup lang="ts">
import type { HighlightEvent } from '@/types/highlight'

defineProps<{ events: HighlightEvent[] }>()

const EMOJI: Record<string, string> = {
  highlight: '🎾',
  ace: '🔥',
  winner: '🏆',
  error: '❌',
}

function eventEmoji(type: string): string {
  return EMOJI[type] ?? '⚡'
}

function formatTime(iso: string): string {
  return new Date(iso).toLocaleTimeString('pt-BR', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  })
}
</script>

<style scoped>
.event-log {
  background: var(--glass-bg);
  backdrop-filter: blur(12px);
  border: 1px solid var(--glass-border);
  border-radius: 16px;
  padding: 1.5rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  max-height: 420px;
}

.log-header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.log-icon { font-size: 1.2rem; }

.log-title {
  font-size: 0.95rem;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0;
  flex: 1;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.log-count {
  background: var(--accent-green);
  color: #000;
  font-size: 0.75rem;
  font-weight: 700;
  padding: 0.15rem 0.55rem;
  border-radius: 999px;
}

.log-list {
  list-style: none;
  margin: 0;
  padding: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  scrollbar-width: thin;
  scrollbar-color: var(--glass-border) transparent;
}

.log-item {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.65rem 0.9rem;
  border-radius: 10px;
  background: rgba(255,255,255,0.03);
  border: 1px solid var(--glass-border);
  transition: all 0.2s ease;
}

.log-item:hover {
  background: rgba(255,255,255,0.06);
  border-color: var(--accent-green);
  transform: translateX(2px);
}

.event-badge { font-size: 1.1rem; flex-shrink: 0; }

.event-info {
  display: flex;
  flex-direction: column;
  flex: 1;
}

.event-type {
  font-size: 0.75rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  color: var(--accent-green);
}

.event-player {
  font-size: 0.8rem;
  color: var(--text-secondary);
}

.event-time {
  font-size: 0.72rem;
  color: #475569;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

/* Variações por tipo */
.event-ace    .event-type { color: #f97316; }
.event-winner .event-type { color: #facc15; }
.event-error  .event-type { color: #ef4444; }

/* Animação de entrada */
.event-list-enter-active { transition: all 0.4s cubic-bezier(0.34,1.56,0.64,1); }
.event-list-enter-from   { opacity: 0; transform: translateY(-16px) scale(0.95); }
.event-list-move         { transition: transform 0.3s ease; }

.log-empty {
  text-align: center;
  color: #475569;
  font-size: 0.85rem;
  padding: 2rem 0;
}
</style>

export function formatRelativeTime(value: string | null) {
  if (!value) {
    return "--";
  }

  const diffMs = Date.now() - new Date(value).getTime();
  if (Number.isNaN(diffMs)) {
    return value;
  }

  const diffMinutes = Math.floor(diffMs / 60000);
  if (diffMinutes < 1) {
    return "just now";
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} min ago`;
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return `${diffHours} hr ago`;
  }

  const diffDays = Math.floor(diffHours / 24);
  return `${diffDays} d ago`;
}

export function formatDateTime(value: string | null) {
  if (!value) {
    return "--";
  }

  return new Date(value).toLocaleString();
}

export function formatCompactNumber(value: number | null) {
  if (value === null) {
    return "--";
  }

  const absolute = Math.abs(value);
  if (absolute >= 1_000_000) {
    return `${(value / 1_000_000).toFixed(2)}M`;
  }
  if (absolute >= 1_000) {
    return `${(value / 1_000).toFixed(1)}K`;
  }
  if (absolute >= 100) {
    return value.toFixed(0);
  }
  if (absolute >= 10) {
    return value.toFixed(1);
  }
  return value.toFixed(2);
}

export function formatProbability(value: number | null) {
  if (value === null) {
    return "--";
  }

  return value.toFixed(2);
}

export function signalContext(signalType: string) {
  if (signalType === "price_movement") {
    return "Unusual short-term volatility.";
  }
  if (signalType === "volume_spike") {
    return "Volume is elevated versus the recent baseline.";
  }
  if (signalType === "liquidity_shift") {
    return "Market depth shifted relative to recent observations.";
  }
  if (signalType === "whale") {
    return "Trade size stands out relative to this market's recent baseline.";
  }
  return "Recent market behavior stands out from the baseline.";
}

export function signalStrengthTier(signalType: string, strength: number) {
  if (signalType === "price_movement") {
    if (strength >= 0.25) return "high";
    if (strength >= 0.15) return "medium";
    return "low";
  }
  if (signalType === "volume_spike") {
    if (strength >= 5) return "high";
    if (strength >= 3) return "medium";
    return "low";
  }
  if (signalType === "liquidity_shift") {
    if (strength >= 0.4) return "high";
    if (strength >= 0.25) return "medium";
    return "low";
  }
  if (signalType === "whale") {
    if (strength >= 8) return "high";
    if (strength >= 4) return "medium";
    return "low";
  }
  return "low";
}

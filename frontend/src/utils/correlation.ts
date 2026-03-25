import type {
  MarketSentimentSummary,
  SentimentDocument,
  SignalItem,
  SnapshotHistoryRow,
} from "../types";

export type CorrelationRow = {
  timestamp: number;
  isoTime: string;
  price: number | null;
  sentiment: number | null;
  docCount: number;
  anomalies: SignalItem[];
  whales: SignalItem[];
  markerPrice: number | null;
};

export type CorrelationView = {
  rows: CorrelationRow[];
  recentHeadlines: SentimentDocument[];
  latestSentiment: number | null;
  sentimentDocCount: number;
  anomalyCount: number;
  whaleCount: number;
};

type PricePoint = {
  timestamp: number;
  price: number;
};

function bucketSizeMs(history: SnapshotHistoryRow[], documents: SentimentDocument[]) {
  const timestamps = [
    ...history.map((row) => new Date(row.observed_at).getTime()),
    ...documents
      .filter((document) => document.published_at)
      .map((document) => new Date(document.published_at as string).getTime()),
  ].filter((value) => Number.isFinite(value));

  if (timestamps.length < 2) {
    return 60 * 60 * 1000;
  }

  const span = Math.max(...timestamps) - Math.min(...timestamps);
  if (span <= 24 * 60 * 60 * 1000) {
    return 60 * 60 * 1000;
  }
  if (span <= 7 * 24 * 60 * 60 * 1000) {
    return 6 * 60 * 60 * 1000;
  }
  return 24 * 60 * 60 * 1000;
}

function normalizeBucketStart(timestamp: number, sizeMs: number) {
  return Math.floor(timestamp / sizeMs) * sizeMs;
}

function findNearestPrice(timestamp: number, pricePoints: PricePoint[]) {
  if (pricePoints.length === 0) {
    return null;
  }

  let bestMatch = pricePoints[0];
  let bestDistance = Math.abs(pricePoints[0].timestamp - timestamp);

  for (const point of pricePoints) {
    const distance = Math.abs(point.timestamp - timestamp);
    if (distance < bestDistance) {
      bestMatch = point;
      bestDistance = distance;
    }
  }

  return bestMatch.price;
}

export function buildCorrelationView(params: {
  history: SnapshotHistoryRow[];
  signals: SignalItem[];
  sentimentSummary: MarketSentimentSummary | null;
  sentimentDocuments: SentimentDocument[];
}): CorrelationView {
  const { history, signals, sentimentSummary, sentimentDocuments } = params;
  const sizeMs = bucketSizeMs(history, sentimentDocuments);

  const pricePoints = history
    .filter((row) => row.last_trade_price !== null)
    .map((row) => ({
      timestamp: new Date(row.observed_at).getTime(),
      price: row.last_trade_price as number,
      isoTime: row.observed_at,
    }))
    .filter((row) => Number.isFinite(row.timestamp))
    .sort((left, right) => left.timestamp - right.timestamp);

  const sentimentBuckets = new Map<number, { sum: number; count: number }>();
  for (const document of sentimentDocuments) {
    if (document.published_at === null || document.sentiment_value === null) {
      continue;
    }
    const timestamp = new Date(document.published_at).getTime();
    if (!Number.isFinite(timestamp)) {
      continue;
    }
    const bucket = normalizeBucketStart(timestamp, sizeMs);
    const current = sentimentBuckets.get(bucket) ?? { sum: 0, count: 0 };
    current.sum += document.sentiment_value;
    current.count += 1;
    sentimentBuckets.set(bucket, current);
  }

  const signalGroups = new Map<number, { anomalies: SignalItem[]; whales: SignalItem[] }>();
  for (const signal of signals) {
    const timestamp = new Date(signal.detected_at).getTime();
    if (!Number.isFinite(timestamp)) {
      continue;
    }
    const current = signalGroups.get(timestamp) ?? { anomalies: [], whales: [] };
    if (signal.signal_type === "whale") {
      current.whales.push(signal);
    } else {
      current.anomalies.push(signal);
    }
    signalGroups.set(timestamp, current);
  }

  const timestamps = new Set<number>();
  for (const point of pricePoints) {
    timestamps.add(point.timestamp);
  }
  for (const bucket of sentimentBuckets.keys()) {
    timestamps.add(bucket);
  }
  for (const timestamp of signalGroups.keys()) {
    timestamps.add(timestamp);
  }

  const rows = Array.from(timestamps)
    .sort((left, right) => left - right)
    .map((timestamp) => {
      const matchingPrice = pricePoints.find((point) => point.timestamp === timestamp);
      const bucket = sentimentBuckets.get(timestamp);
      const groupedSignals = signalGroups.get(timestamp) ?? { anomalies: [], whales: [] };

      return {
        timestamp,
        isoTime: new Date(timestamp).toISOString(),
        price: matchingPrice?.price ?? null,
        sentiment: bucket ? bucket.sum / bucket.count : null,
        docCount: bucket?.count ?? 0,
        anomalies: groupedSignals.anomalies,
        whales: groupedSignals.whales,
        markerPrice:
          groupedSignals.anomalies.length > 0 || groupedSignals.whales.length > 0
            ? findNearestPrice(timestamp, pricePoints)
            : null,
      };
    });

  const recentHeadlines = [...sentimentDocuments]
    .sort((left, right) => {
      const leftTime = left.published_at ? new Date(left.published_at).getTime() : 0;
      const rightTime = right.published_at ? new Date(right.published_at).getTime() : 0;
      return rightTime - leftTime;
    })
    .slice(0, 5);

  const latestSentiment =
    [...rows].reverse().find((row) => row.sentiment !== null)?.sentiment ??
    sentimentSummary?.avg_sentiment ??
    null;

  return {
    rows,
    recentHeadlines,
    latestSentiment,
    sentimentDocCount: sentimentSummary?.doc_count ?? recentHeadlines.length,
    anomalyCount: signals.filter((signal) => signal.signal_type !== "whale").length,
    whaleCount: signals.filter((signal) => signal.signal_type === "whale").length,
  };
}

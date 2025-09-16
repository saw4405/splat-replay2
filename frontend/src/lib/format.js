export function formatTimestamp(timestamp) {
  if (timestamp == null) {
    return "-";
  }
  const date = new Date(timestamp * 1000);
  return date.toLocaleString();
}

export function formatLength(lengthSeconds) {
  if (lengthSeconds == null) {
    return "-";
  }
  const minutes = Math.floor(lengthSeconds / 60);
  const seconds = Math.round(lengthSeconds % 60)
    .toString()
    .padStart(2, "0");
  return `${minutes}:${seconds}`;
}

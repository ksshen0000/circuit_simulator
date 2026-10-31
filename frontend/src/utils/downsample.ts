/** Largest-Triangle-Three-Buckets downsampling for waveform charts. */
export function lttb<T extends { x: number; y: number }>(data: T[], threshold: number): T[] {
  if (threshold >= data.length || threshold <= 2) return data;
  const sampled: T[] = [data[0]];
  const bucketSize = (data.length - 2) / (threshold - 2);
  let previousIndex = 0;

  for (let bucket = 0; bucket < threshold - 2; bucket += 1) {
    const averageStart = Math.floor((bucket + 1) * bucketSize) + 1;
    const averageEnd = Math.min(Math.floor((bucket + 2) * bucketSize) + 1, data.length);
    let averageX = 0;
    let averageY = 0;
    const averageCount = Math.max(1, averageEnd - averageStart);
    for (let i = averageStart; i < averageEnd; i += 1) {
      averageX += data[i].x;
      averageY += data[i].y;
    }
    averageX /= averageCount;
    averageY /= averageCount;

    const rangeStart = Math.floor(bucket * bucketSize) + 1;
    const rangeEnd = Math.min(Math.floor((bucket + 1) * bucketSize) + 1, data.length - 1);
    const pointA = data[previousIndex];
    let maxArea = -1;
    let nextIndex = rangeStart;
    for (let i = rangeStart; i < rangeEnd; i += 1) {
      const area = Math.abs(
        (pointA.x - averageX) * (data[i].y - pointA.y)
        - (pointA.x - data[i].x) * (averageY - pointA.y),
      );
      if (area > maxArea) {
        maxArea = area;
        nextIndex = i;
      }
    }
    sampled.push(data[nextIndex]);
    previousIndex = nextIndex;
  }
  sampled.push(data[data.length - 1]);
  return sampled;
}

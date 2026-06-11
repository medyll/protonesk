export function asyncIterable<T>(items: T[]): AsyncIterable<T> {
  return {
    [Symbol.asyncIterator]() {
      let i = 0;
      return {
        next: async () => (i < items.length ? { value: items[i++], done: false } : { value: undefined, done: true }),
      };
    },
  } as AsyncIterable<T>;
}

/**
 * tree-kill 类型声明
 */
declare module 'tree-kill' {
  function kill(pid: number, callback?: (err?: Error) => void): void;
  function kill(pid: number, signal: string, callback?: (err?: Error) => void): void;
  export = kill;
}

/**
 * Unified diff 解析器：将 difflib.unified_diff 输出解析为结构化行数据。
 *
 * 对连续的 del+add 行进行配对，生成 pair 类型（左右对比）。
 * 未配对的 del 或 add 保留原样。
 */

export type DiffItemType = "hunk" | "add" | "del" | "ctx" | "pair"

export interface DiffItem {
  type: DiffItemType
  content?: string
  old?: string
  new?: string
}

export function parseDiffLines(diffText: string): DiffItem[] {
  if (!diffText || !diffText.trim()) return []

  const lines = diffText.split("\n")
  const result: DiffItem[] = []

  // 先分类所有行
  const classified: DiffItem[] = []
  for (const line of lines) {
    if (line.startsWith("---") || line.startsWith("+++")) {
      continue
    } else if (line.startsWith("@@")) {
      classified.push({ type: "hunk", content: line })
    } else if (line.startsWith("+")) {
      classified.push({ type: "add", content: line.slice(1) })
    } else if (line.startsWith("-")) {
      classified.push({ type: "del", content: line.slice(1) })
    } else if (line.startsWith(" ")) {
      classified.push({ type: "ctx", content: line.slice(1) })
    } else {
      classified.push({ type: "ctx", content: line })
    }
  }

  // 配对连续 del+add 行
  let i = 0
  while (i < classified.length) {
    const item = classified[i]
    if (item.type === "del") {
      // 收集连续 del 行
      const dels: DiffItem[] = [item]
      let j = i + 1
      while (j < classified.length && classified[j].type === "del") {
        dels.push(classified[j])
        j++
      }
      // 检查后面是否有连续 add 行
      const adds: DiffItem[] = []
      let k = j
      while (k < classified.length && classified[k].type === "add") {
        adds.push(classified[k])
        k++
      }
      if (adds.length > 0) {
        // 配对
        const maxLen = Math.max(dels.length, adds.length)
        for (let idx = 0; idx < maxLen; idx++) {
          const old = idx < dels.length ? dels[idx].content ?? "" : ""
          const newVal = idx < adds.length ? adds[idx].content ?? "" : ""
          if (old && newVal) {
            result.push({ type: "pair", old, new: newVal })
          } else if (newVal) {
            result.push({ type: "add", content: newVal })
          } else if (old) {
            result.push({ type: "del", content: old })
          }
        }
        i = k
      } else {
        // 无配对 add，直接输出 del
        for (const d of dels) result.push(d)
        i = j
      }
    } else if (item.type === "add") {
      // 前面没有 del 配对的 add
      result.push(item)
      i++
    } else {
      // hunk / ctx
      result.push(item)
      i++
    }
  }

  return result
}

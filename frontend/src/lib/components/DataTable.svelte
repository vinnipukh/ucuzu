<script lang="ts">
  export interface Column {
    key: string;
    label: string;
    align?: 'left' | 'right' | 'center';
    format?: (value: unknown) => string;
    monospace?: boolean;
  }

  interface Props {
    columns: Column[];
    rows: Record<string, unknown>[];
    emptyMessage?: string;
    maxHeight?: number;
  }

  let { columns, rows, emptyMessage = 'No records returned.', maxHeight = 420 }: Props = $props();

  function rowKey(row: Record<string, unknown>, index: number): string {
    const first = columns[0]?.key;
    return first ? `${row[first]}-${index}` : String(index);
  }

  function cellAlign(column: Column): string {
    return column.align ?? 'left';
  }
</script>

{#if rows.length === 0}
  <p class="empty">{emptyMessage}</p>
{:else}
  <div class="table-wrap" style={`max-height: ${maxHeight}px`}>
    <table>
      <thead>
        <tr>
          {#each columns as column (column.key)}
            <th style={`text-align: ${cellAlign(column)}`}>{column.label}</th>
          {/each}
        </tr>
      </thead>
      <tbody>
        {#each rows as row, index (rowKey(row, index))}
          <tr>
            {#each columns as column (column.key)}
              <td
                style={`text-align: ${cellAlign(column)}`}
                class:mono={column.monospace ?? false}
              >
                {column.format ? column.format(row[column.key]) : String(row[column.key] ?? '')}
              </td>
            {/each}
          </tr>
        {/each}
      </tbody>
    </table>
  </div>
{/if}

<style>
  .empty {
    padding: 12px 0;
    color: var(--color-muted-foreground);
    font-size: 0.86rem;
  }
  .table-wrap {
    overflow: auto;
    border: 1px solid var(--color-border);
    border-radius: 14px;
    background: var(--color-card);
    box-shadow: var(--shadow-paper-small);
  }
  table {
    width: 100%;
    min-width: 620px;
    border-collapse: collapse;
    font-size: 0.8rem;
  }
  thead th {
    position: sticky;
    top: 0;
    z-index: 1;
    padding: 11px 13px 10px;
    border-bottom: 1px solid var(--color-line);
    background: var(--color-muted);
    color: var(--color-muted-foreground);
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.07em;
    text-transform: uppercase;
    white-space: nowrap;
  }
  thead th:first-child {
    border-top-left-radius: 13px;
  }
  thead th:last-child {
    border-top-right-radius: 13px;
  }
  tbody td {
    padding: 9px 13px;
    border-bottom: 1px solid var(--color-border);
    color: var(--color-card-foreground);
    font-variant-numeric: tabular-nums;
    vertical-align: top;
  }
  tbody tr:last-child td {
    border-bottom: none;
  }
  tbody tr:hover td {
    background: var(--color-muted);
  }
  td.mono {
    font-family: var(--font-mono);
  }
</style>

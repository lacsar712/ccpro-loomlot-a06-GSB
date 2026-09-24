<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let houses = [];
  let vats = [];
  let lots = [];
  let checks = [];
  let rows = [];
  let bindings = [];
  let error = '';
  let expanded = null;
  let bindCheckId = '';

  let form = { dyeHouseId: '', slotCode: '', capacity: 10, isActive: true };
  let editing = null;

  $: isAdmin = $user?.role === 'admin';

  async function load() {
    error = '';
    try {
      [houses, vats, lots, checks, rows, bindings] = await Promise.all([
        api('/dye-houses'),
        api('/vats'),
        api('/dye-lots'),
        api('/fastness-checks'),
        api('/sample-slots'),
        api('/sample-slots/bindings'),
      ]);
      if (!form.dyeHouseId && houses.length) form.dyeHouseId = String(houses[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  function houseName(id) {
    return houses.find((h) => h.id === id)?.name || id;
  }

  // 色牢度 → 染坊（色牢度→染程→染缸→染坊）
  function checkHouseId(checkId) {
    const ck = checks.find((x) => x.id === checkId);
    const lot = lots.find((l) => l.id === ck?.dyeLotId);
    return vats.find((v) => v.id === lot?.vatId)?.dyeHouseId;
  }

  $: boundCheckIds = new Set(bindings.map((b) => b.fastnessCheckId));

  function slotBindings(slotId) {
    return bindings.filter((b) => b.slotId === slotId);
  }

  // 可入格候选：同坊、尚未入格
  function eligibleChecks(slot) {
    return checks.filter(
      (x) => !boundCheckIds.has(x.id) && checkHouseId(x.id) === slot.dyeHouseId
    );
  }

  function checkLabel(id) {
    const ck = checks.find((x) => x.id === id);
    if (!ck) return `#${id}`;
    const lot = lots.find((l) => l.id === ck.dyeLotId);
    return `#${ck.id} ${lot ? lot.recipeName : ''} 耐洗${ck.washFastness}`;
  }

  async function save() {
    error = '';
    try {
      const body = {
        dyeHouseId: Number(form.dyeHouseId),
        slotCode: form.slotCode.trim(),
        capacity: Number(form.capacity),
        isActive: !!form.isActive,
      };
      if (editing) {
        await api(`/sample-slots/${editing}`, { method: 'PUT', body: JSON.stringify(body) });
      } else {
        await api('/sample-slots', { method: 'POST', body: JSON.stringify(body) });
      }
      editing = null;
      form = { dyeHouseId: form.dyeHouseId, slotCode: '', capacity: 10, isActive: true };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(row) {
    editing = row.id;
    form = {
      dyeHouseId: String(row.dyeHouseId),
      slotCode: row.slotCode,
      capacity: row.capacity,
      isActive: row.isActive,
    };
  }

  function toggleExpand(row) {
    expanded = expanded === row.id ? null : row.id;
    const first = eligibleChecks(row)[0];
    bindCheckId = first ? String(first.id) : '';
  }

  async function bind(slot) {
    error = '';
    if (!bindCheckId) {
      error = '该坊暂无可入格的色牢度（未入格且属于本坊）';
      return;
    }
    try {
      await api(`/sample-slots/${slot.id}/bindings`, {
        method: 'POST',
        body: JSON.stringify({ fastnessCheckId: Number(bindCheckId) }),
      });
      await load();
      const first = eligibleChecks(slot)[0];
      bindCheckId = first ? String(first.id) : '';
    } catch (e) {
      error = e.message;
    }
  }

  async function unbind(bindingId) {
    error = '';
    try {
      await api(`/sample-slots/bindings/${bindingId}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function toggleActive(row) {
    error = '';
    try {
      await api(`/sample-slots/${row.id}`, {
        method: 'PUT',
        body: JSON.stringify({ isActive: !row.isActive }),
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function remove(row) {
    if (!confirm('确认删除该留样格位？')) return;
    error = '';
    try {
      await api(`/sample-slots/${row.id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">留样格</h1>
<p class="page-sub">
  色牢度留样入格互证：一条色牢度只能入一次、格满不可再入。某坊启用格位<b>已存合计大于 0</b>
  时，该坊新建染程布重上限由 100kg 降为 <b>50kg</b>；全部取出清零后恢复。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >所属染坊
      <select bind:value={form.dyeHouseId} disabled={editing !== null}>
        {#each houses as h}
          <option value={String(h.id)}>{h.name}</option>
        {/each}
      </select>
    </label>
    <label>格位码 <input bind:value={form.slotCode} placeholder="同坊唯一" /></label>
    <label>可存条数 <input type="number" min="1" step="1" bind:value={form.capacity} /></label>
    <label class="check-lbl"
      ><span
        ><input
          type="checkbox"
          bind:checked={form.isActive}
          disabled={editing !== null && !isAdmin}
        />
        启用{editing !== null && !isAdmin ? '（停用需主管）' : ''}</span
      ></label
    >
  </div>
  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>{editing ? '保存修改' : '新建格位'}</button>
    {#if editing}
      <button
        class="btn ghost"
        type="button"
        on:click={() => {
          editing = null;
          form = { dyeHouseId: form.dyeHouseId, slotCode: '', capacity: 10, isActive: true };
        }}>取消</button
      >
    {/if}
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染坊</th>
        <th>格位码</th>
        <th>已存 / 可存</th>
        <th>状态</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{houseName(row.dyeHouseId)}</td>
          <td>{row.slotCode}</td>
          <td>
            <span class:full={row.storedCount >= row.capacity}>{row.storedCount} / {row.capacity}</span>
          </td>
          <td>
            <span class="badge {row.isActive ? 'ready' : 'drain'}">{row.isActive ? '启用' : '停用'}</span>
          </td>
          <td class="row-actions">
            {#if row.isActive}
              <button class="btn small" type="button" on:click={() => toggleExpand(row)}>
                {expanded === row.id ? '收起' : '入格'}
              </button>
            {/if}
            <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>编辑</button>
            {#if isAdmin}
              <button class="btn ghost small" type="button" on:click={() => toggleActive(row)}>
                {row.isActive ? '停用' : '启用'}
              </button>
            {/if}
            <button class="btn danger small" type="button" on:click={() => remove(row)}>删除</button>
          </td>
        </tr>
        {#if expanded === row.id}
          <tr class="bind-row">
            <td colspan="6">
              <div class="bind-box">
                <div class="toolbar" style="margin-bottom:0.5rem;">
                  <select bind:value={bindCheckId}>
                    {#each eligibleChecks(row) as ck}
                      <option value={String(ck.id)}>{checkLabel(ck.id)}</option>
                    {/each}
                  </select>
                  <button class="btn small" type="button" on:click={() => bind(row)}>确认入格</button>
                  <span class="hint-text"
                    >仅列本坊且未入格的色牢度；已满 {row.storedCount}/{row.capacity}</span
                  >
                </div>
                {#if slotBindings(row.id).length}
                  <ul class="bind-list">
                    {#each slotBindings(row.id) as b}
                      <li>
                        <span>{checkLabel(b.fastnessCheckId)}</span>
                        <span class="hint-text">{new Date(b.boundAt).toLocaleString()}</span>
                        <button class="btn ghost small" type="button" on:click={() => unbind(b.id)}>
                          取出
                        </button>
                      </li>
                    {/each}
                  </ul>
                {:else}
                  <p class="hint-text" style="margin:0;">暂无留样</p>
                {/if}
              </div>
            </td>
          </tr>
        {/if}
      {/each}
    </tbody>
  </table>
  {#if !isAdmin}
    <p class="hint-text" style="margin-top:0.75rem;">操作员可入格 / 取出；停用格位需染坊主管，且格位已存必须为 0。</p>
  {/if}
</div>

<style>
  .check-lbl {
    justify-content: flex-end;
  }
  .check-lbl span {
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }
  .check-lbl input {
    width: auto;
  }
  .full {
    color: var(--danger);
    font-weight: 600;
  }
  .bind-row td {
    background: rgba(18, 10, 42, 0.45);
  }
  .bind-box {
    padding: 0.4rem 0.2rem;
  }
  .hint-text {
    color: var(--indigo-mist);
    font-size: 0.78rem;
  }
  .bind-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
  }
  .bind-list li {
    display: flex;
    align-items: center;
    gap: 0.8rem;
    font-size: 0.85rem;
  }
</style>

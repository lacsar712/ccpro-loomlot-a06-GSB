<script>
  import { onMount } from 'svelte';
  import { api } from '../lib/api.js';
  import { user } from '../lib/auth.js';

  let houses = [];
  let slots = [];
  let checks = [];
  let lots = [];
  let error = '';
  let form = { dyeHouseId: '', slotCode: '', capacity: 20, enabled: true };
  let pick = {};
  let editing = null;

  async function load() {
    error = '';
    try {
      [houses, slots, checks, lots] = await Promise.all([
        api('/dye-houses'),
        api('/sample-slots'),
        api('/fastness-checks'),
        api('/dye-lots'),
      ]);
      if (!form.dyeHouseId && houses.length) form.dyeHouseId = String(houses[0].id);
      slots.forEach((s) => {
        if (pick[s.id] === undefined) pick[s.id] = '';
      });
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  $: isAdmin = $user?.role === 'admin';
  $: occupiedCount = slots.filter((s) => s.storedCount > 0).length;
  $: unboundChecks = checks.filter((c) => c.sampleSlotId == null);

  function houseName(id) {
    return houses.find((h) => h.id === id)?.name || id;
  }

  function checkLabel(c) {
    const lot = lots.find((l) => l.id === c.dyeLotId);
    const base = lot ? `${lot.recipeName} (#${lot.id})` : `染程 #${c.dyeLotId}`;
    return `抽检#${c.id} · ${base} · 耐洗${c.washFastness}`;
  }

  function boundChecks(slotId) {
    return checks.filter((c) => c.sampleSlotId === slotId);
  }

  // 该坊存在启用且已存>0 的格位时，新建染程布重上限降为 50kg
  function houseCapped(houseId) {
    return slots.some((s) => s.dyeHouseId === houseId && s.enabled && s.storedCount > 0);
  }

  async function save() {
    error = '';
    try {
      const body = {
        dyeHouseId: Number(form.dyeHouseId),
        slotCode: form.slotCode.trim(),
        capacity: Number(form.capacity),
        enabled: form.enabled,
      };
      if (editing) {
        await api(`/sample-slots/${editing}`, {
          method: 'PUT',
          body: JSON.stringify({ slotCode: body.slotCode, capacity: body.capacity }),
        });
      } else {
        await api('/sample-slots', { method: 'POST', body: JSON.stringify(body) });
      }
      editing = null;
      form = { dyeHouseId: form.dyeHouseId, slotCode: '', capacity: 20, enabled: true };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(slot) {
    editing = slot.id;
    form = {
      dyeHouseId: String(slot.dyeHouseId),
      slotCode: slot.slotCode,
      capacity: slot.capacity,
      enabled: slot.enabled,
    };
  }

  async function toggle(slot, enabled) {
    error = '';
    try {
      await api(`/sample-slots/${slot.id}`, {
        method: 'PUT',
        body: JSON.stringify({ enabled }),
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function remove(slot) {
    if (!confirm(`确认删除格位「${slot.slotCode}」？`)) return;
    error = '';
    try {
      await api(`/sample-slots/${slot.id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function store(slot) {
    error = '';
    try {
      await api(`/sample-slots/${slot.id}/store`, {
        method: 'POST',
        body: JSON.stringify({ fastnessCheckId: Number(pick[slot.id]) }),
      });
      pick[slot.id] = '';
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  async function unstore(slot, checkId) {
    error = '';
    try {
      await api(`/sample-slots/${slot.id}/unstore`, {
        method: 'POST',
        body: JSON.stringify({ fastnessCheckId: checkId }),
      });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">留样格</h1>
<p class="page-sub">
  色牢度入格留样：一条色牢度只能入一次，入格已存加一、满格不可再入。某坊启用格位已存合计大于 0 时，该坊新建染程布重上限降为
  <strong>50 千克</strong>；已存全部清零后恢复原规则。
</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="sum">
    已存大于 0 的格位数：<strong>{occupiedCount}</strong>
    <span class="muted">（与总览看板统计一致）</span>
  </div>
</div>

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
    <label>格位码 <input bind:value={form.slotCode} placeholder="如 R-01" /></label>
    <label>可存条数 <input type="number" min="1" step="1" bind:value={form.capacity} /></label>
    {#if !editing}
      <label class="check">
        <input type="checkbox" bind:checked={form.enabled} /> 启用
      </label>
    {/if}
  </div>
  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>{editing ? '保存修改' : '新建格位'}</button>
    {#if editing}
      <button
        class="btn ghost"
        type="button"
        on:click={() => {
          editing = null;
          form = { ...form, slotCode: '', capacity: 20, enabled: true };
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
        <th>已存/可存</th>
        <th>状态</th>
        <th>入格留样</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each slots as slot}
        <tr class:off={!slot.enabled}>
          <td>{slot.id}</td>
          <td>
            {houseName(slot.dyeHouseId)}
            {#if houseCapped(slot.dyeHouseId)}<span class="cap-tag">该坊限 50kg</span>{/if}
          </td>
          <td>{slot.slotCode}</td>
          <td>
            <span class="count" class:full={slot.storedCount >= slot.capacity}
              >{slot.storedCount}/{slot.capacity}</span
            >
          </td>
          <td>
            <span class="badge {slot.enabled ? 'ready' : 'drain'}">{slot.enabled ? '启用' : '停用'}</span>
          </td>
          <td class="store-cell">
            {#each boundChecks(slot.id) as c}
              <span class="chip">
                {checkLabel(c)}
                <button class="link-btn" type="button" on:click={() => unstore(slot, c.id)}>取出</button>
              </span>
            {/each}
            {#if slot.enabled}
              <div class="store-row">
                <select bind:value={pick[slot.id]}>
                  <option value="">选择色牢度入格…</option>
                  {#each unboundChecks as c}
                    <option value={String(c.id)}>{checkLabel(c)}</option>
                  {/each}
                </select>
                <button
                  class="btn small"
                  type="button"
                  disabled={!pick[slot.id] || slot.storedCount >= slot.capacity}
                  on:click={() => store(slot)}>入格</button
                >
              </div>
            {/if}
            {#if slot.storedCount >= slot.capacity}<span class="full-note">已满格</span>{/if}
          </td>
          <td class="row-actions">
            <button class="btn ghost small" type="button" on:click={() => startEdit(slot)}>编辑</button>
            {#if slot.enabled}
              <button
                class="btn ghost small"
                type="button"
                disabled={!isAdmin || slot.storedCount > 0}
                title={!isAdmin ? '停用需染坊主管' : slot.storedCount > 0 ? '须先清空留样' : ''}
                on:click={() => toggle(slot, false)}>停用</button
              >
            {:else}
              <button class="btn ghost small" type="button" on:click={() => toggle(slot, true)}
                >启用</button
              >
            {/if}
            <button
              class="btn danger small"
              type="button"
              disabled={slot.storedCount > 0}
              on:click={() => remove(slot)}>删除</button
            >
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  .sum {
    font-size: 0.95rem;
  }

  .muted {
    color: var(--indigo-mist);
    font-size: 0.82rem;
  }

  .check {
    flex-direction: row;
    align-items: center;
    gap: 0.4rem;
  }

  .cap-tag {
    margin-left: 0.4rem;
    padding: 0.05rem 0.4rem;
    font-size: 0.7rem;
    border-radius: 2px;
    color: #ffd9a0;
    background: rgba(214, 137, 16, 0.18);
    border: 1px solid rgba(214, 137, 16, 0.4);
  }

  .count.full {
    color: var(--danger, #e88);
    font-weight: 600;
  }

  .full-note {
    color: var(--danger, #e88);
    font-size: 0.75rem;
  }

  .store-cell {
    min-width: 260px;
  }

  .chip {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    margin: 0.1rem 0.25rem 0.1rem 0;
    padding: 0.1rem 0.45rem;
    font-size: 0.75rem;
    border-radius: 2px;
    background: rgba(107, 92, 231, 0.15);
    border: 1px solid rgba(107, 92, 231, 0.35);
    white-space: nowrap;
  }

  .link-btn {
    background: none;
    border: none;
    padding: 0;
    color: var(--indigo-mist);
    text-decoration: underline;
    cursor: pointer;
    font-size: 0.72rem;
  }

  .link-btn:hover {
    color: white;
  }

  .store-row {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.3rem;
  }

  .store-row select {
    flex: 1;
    min-width: 180px;
  }

  tr.off {
    opacity: 0.6;
  }
</style>

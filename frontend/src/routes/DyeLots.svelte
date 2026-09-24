<script>
  import { onMount } from 'svelte';
  import { api, VAT_STATUS, toLocalInput, fromLocalInput } from '../lib/api.js';

  let vats = [];
  let rows = [];
  let slots = [];
  let error = '';
  let form = {
    vatId: '',
    recipeName: '',
    fabricKg: 20,
    startedAt: toLocalInput(new Date().toISOString()),
    operatorName: '染程操作员',
  };
  let editing = null;

  async function load() {
    error = '';
    try {
      [vats, rows, slots] = await Promise.all([
        api('/vats'),
        api('/dye-lots'),
        api('/sample-slots'),
      ]);
      const usable = vats.filter((v) => v.status === 'ready' || v.status === 'dyeing');
      if (!form.vatId && usable.length) form.vatId = String(usable[0].id);
      else if (!form.vatId && vats.length) form.vatId = String(vats[0].id);
    } catch (e) {
      error = e.message;
    }
  }

  onMount(load);

  // 该坊启用格位已存合计是否大于 0
  $: occupiedHouseIds = new Set(
    slots.filter((s) => s.isActive && s.storedCount > 0).map((s) => s.dyeHouseId)
  );

  $: selectedVat = vats.find((v) => v.id === Number(form.vatId));
  $: fabricLimit = selectedVat
    ? occupiedHouseIds.has(selectedVat.dyeHouseId)
      ? 50
      : 100
    : 100;
  $: limitLowered = fabricLimit === 50;

  function vatLabel(id) {
    const v = vats.find((x) => x.id === id);
    if (!v) return id;
    return `${v.vatCode}（${VAT_STATUS[v.status] || v.status}）`;
  }

  async function save() {
    error = '';
    if (Number(form.fabricKg) > fabricLimit) {
      error = limitLowered
        ? `布重超过该坊当前上限 50 千克（因留样占位），请改至 50kg 以内或先取出留样`
        : `布重超过新建染程布重上限 100 千克`;
      return;
    }
    try {
      const body = {
        vatId: Number(form.vatId),
        recipeName: form.recipeName.trim(),
        fabricKg: Number(form.fabricKg),
        startedAt: fromLocalInput(form.startedAt),
        operatorName: form.operatorName.trim(),
      };
      if (editing) {
        await api(`/dye-lots/${editing}`, { method: 'PUT', body: JSON.stringify(body) });
      } else {
        await api('/dye-lots', { method: 'POST', body: JSON.stringify(body) });
      }
      editing = null;
      form = {
        ...form,
        recipeName: '',
        fabricKg: 20,
        startedAt: toLocalInput(new Date().toISOString()),
      };
      await load();
    } catch (e) {
      error = e.message;
    }
  }

  function startEdit(row) {
    editing = row.id;
    form = {
      vatId: String(row.vatId),
      recipeName: row.recipeName,
      fabricKg: row.fabricKg,
      startedAt: toLocalInput(row.startedAt),
      operatorName: row.operatorName,
    };
  }

  async function remove(id) {
    if (!confirm('确认删除该染程？')) return;
    error = '';
    try {
      await api(`/dye-lots/${id}`, { method: 'DELETE' });
      await load();
    } catch (e) {
      error = e.message;
    }
  }
</script>

<h1 class="page-title">染程</h1>
<p class="page-sub">仅 ready / dyeing 染缸可开缸；提交后染缸自动变为染色中。</p>

<div class="panel" style="margin-bottom:1rem;">
  <div class="form-grid">
    <label
      >染缸
      <select bind:value={form.vatId}>
        {#each vats as v}
          <option value={String(v.id)}
            >{v.vatCode} · {VAT_STATUS[v.status] || v.status} · {v.fiberType}</option
          >
        {/each}
      </select>
    </label>
    <label>配方名 <input bind:value={form.recipeName} /></label>
    <label>
      布料 kg（上限 {fabricLimit}）
      <input
        type="number"
        step="0.1"
        min="0.1"
        max={fabricLimit}
        class:over={Number(form.fabricKg) > fabricLimit}
        bind:value={form.fabricKg}
      />
    </label>
    <label>开始时间 <input type="datetime-local" bind:value={form.startedAt} /></label>
    <label>操作员 <input bind:value={form.operatorName} /></label>
  </div>
  {#if limitLowered}
    <p class="err" style="margin:0 0 0.6rem;">
      该染坊启用格位已有留样占位，新建染程布重上限降为 50 千克；留样全部取出清零后恢复 100 千克。
    </p>
  {/if}
  <div class="toolbar">
    <button class="btn" type="button" on:click={save}>{editing ? '保存修改' : '新建染程'}</button>
    {#if editing}
      <button class="btn ghost" type="button" on:click={() => (editing = null)}>取消</button>
    {/if}
  </div>
  {#if error}<p class="err">{error}</p>{/if}
</div>

<div class="panel">
  <table>
    <thead>
      <tr>
        <th>ID</th>
        <th>染缸</th>
        <th>配方</th>
        <th>布料 kg</th>
        <th>开始</th>
        <th>操作员</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      {#each rows as row}
        <tr>
          <td>{row.id}</td>
          <td>{vatLabel(row.vatId)}</td>
          <td>{row.recipeName}</td>
          <td>{row.fabricKg}</td>
          <td>{new Date(row.startedAt).toLocaleString()}</td>
          <td>{row.operatorName}</td>
          <td class="row-actions">
            <button class="btn ghost small" type="button" on:click={() => startEdit(row)}>编辑</button>
            <button class="btn danger small" type="button" on:click={() => remove(row.id)}>删除</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
</div>

<style>
  input.over {
    border-color: var(--danger);
    outline-color: var(--danger);
  }
</style>

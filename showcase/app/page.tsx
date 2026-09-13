'use client';

import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';

type Health = 'OK' | 'WARN' | 'BAD' | 'UNK';
type Density = 'full' | 'compact' | 'tight';
type Metric = { label: string; value: string; status: Health; icon?: string; history?: boolean };
type TableKind = 'generic' | 'display' | 'devices' | 'ports' | 'input';
type Section = {
  key: string; title: string; subtitle: string; status: Health; summary: string; help: string;
  field?: string; metrics?: Metric[];
  table?: { title?: string; kind: TableKind; headers: string[]; rows: string[][] };
};

const sections: Section[] = [
  { key: 'performance', title: 'Performance', subtitle: 'Thermals / Load', status: 'OK', summary: 'CPU utilization: 18% | Load: 1.42 | Thermal pressure: Nominal', field: 'CPU utilization: 18% | Load: 1.42 | Thermal pressure: Nominal', help: 'Thermals and power residency from macOS sensor tooling (best-effort). Some sensor sources may be unavailable on certain macOS builds.', metrics: [
    { label: 'CPU temperature', value: '47 °C', status: 'OK', icon: 'thermometer', history: true }, { label: 'GPU temperature', value: '43 °C', status: 'OK', icon: 'gpu', history: true }, { label: 'CPU utilization', value: '18%', status: 'OK', icon: 'cpu', history: true }, { label: 'Load average', value: '1.42', status: 'OK', history: true }, { label: 'Thermal pressure', value: 'Nominal', status: 'OK', icon: 'thermometer' },
  ] },
  { key: 'general', title: 'General Info', subtitle: 'Model / OS', status: 'OK', summary: 'Mac Studio | Apple M2 Max | macOS Sequoia 15.5 | DEMO-C02X9Q2', field: 'Mac Studio | Apple M2 Max | macOS Sequoia 15.5 | DEMO-C02X9Q2', help: 'Basic machine identity (model, chip, OS version). Used to interpret other sections.' },
  { key: 'security', title: 'Security', subtitle: 'FileVault / SIP', status: 'WARN', summary: 'FileVault: Off | SIP: Enabled | Gatekeeper: Enabled | Firewall: Enabled', help: 'Security controls reported by macOS.', metrics: [
    { label: 'FileVault', value: 'Off', status: 'WARN' }, { label: 'SIP', value: 'Enabled', status: 'OK' }, { label: 'Gatekeeper', value: 'Enabled', status: 'OK' }, { label: 'Firewall', value: 'Enabled', status: 'OK' },
  ] },
  { key: 'system', title: 'System', subtitle: 'Storage / Memory', status: 'OK', summary: 'Disk free: 63% | Memory free: 54%', help: 'Storage and memory capacity at a glance.', metrics: [
    { label: 'Disk free', value: '63%', status: 'OK', history: true }, { label: 'Memory free', value: '54%', status: 'OK', history: true },
  ] },
  { key: 'processes', title: 'Processes', subtitle: 'Top CPU / MEM', status: 'OK', summary: 'Top offenders (rows: 10)', field: 'Top offenders (rows: 10)', help: 'Processes using the most CPU or memory.', table: { title: 'Table', kind: 'generic', headers: ['Type', 'PID', 'CPU%', 'MEM%', 'Command'], rows: [
    ['CPU', '412', '7.4', '2.8', 'WindowServer'], ['MEM', '988', '4.1', '6.2', 'Safari'], ['CPU', '1842', '1.2', '0.4', 'Mac Health Checkup'], ['CPU', '0', '0.8', '0.7', 'kernel_task'], ['MEM', '1042', '0.4', '3.1', 'Finder'], ['CPU', '1198', '0.3', '1.8', 'Code'], ['MEM', '622', '0.2', '1.5', 'Mail'], ['CPU', '941', '0.2', '1.2', 'Music'], ['MEM', '788', '0.1', '1.0', 'Messages'], ['CPU', '321', '0.1', '0.8', 'ControlCenter'],
  ] } },
  { key: 'startup', title: 'Startup', subtitle: 'Launch Agents', status: 'OK', summary: '6 items (showing 6)', field: '6 items (showing 6)', help: 'Login items, launch agents, and launch daemons.', table: { title: 'Table', kind: 'generic', headers: ['Type', 'Label', 'State', 'Path'], rows: [
    ['Login Item', 'Rectangle', 'Enabled', '/Applications/Rectangle.app'], ['Login Item', 'Dropbox', 'Enabled', '/Applications/Dropbox.app'], ['User Agent', 'com.demo.backup', 'Loaded', '~/Library/LaunchAgents'], ['User Agent', 'com.demo.sync', 'Loaded', '~/Library/LaunchAgents'], ['System', 'com.apple.TimeMachine', 'Loaded', '/System/Library/LaunchDaemons'], ['System', 'com.apple.metadata', 'Loaded', '/System/Library/LaunchDaemons'],
  ] } },
  { key: 'backups', title: 'Backups', subtitle: 'Time Machine', status: 'OK', summary: 'Last backup: Today at 9:42 AM | Automatic backups: On', help: 'Time Machine configuration and recent backup status.', metrics: [
    { label: 'Configured', value: 'Yes', status: 'OK' }, { label: 'Last backup', value: 'Today at 9:42 AM', status: 'OK' }, { label: 'Destination', value: 'Backup Disk', status: 'OK' }, { label: 'Automatic backups', value: 'On', status: 'OK' },
  ] },
  { key: 'updates', title: 'Updates', subtitle: 'Software Update', status: 'WARN', summary: 'Updates: 1 available', help: 'Available macOS software updates.', metrics: [
    { label: 'Current version', value: 'macOS 15.5', status: 'OK' }, { label: 'Available update', value: 'macOS 15.5.1', status: 'WARN' }, { label: 'Automatic checks', value: 'On', status: 'OK' },
  ] },
  { key: 'power', title: 'Power', subtitle: 'Adapter / Temps', status: 'OK', summary: 'AC Power | CPU: 47 °C | GPU: 43 °C', help: 'Power source and temperature readings.', metrics: [
    { label: 'Power source', value: 'AC Power', status: 'OK', icon: 'power' }, { label: 'CPU temperature', value: '47 °C', status: 'OK', icon: 'thermometer', history: true }, { label: 'GPU temperature', value: '43 °C', status: 'OK', icon: 'gpu', history: true }, { label: 'Thermal state', value: 'Nominal', status: 'OK', icon: 'thermometer' },
  ] },
  { key: 'fan', title: 'Fans', subtitle: 'Status', status: 'OK', summary: 'Fan 1: 1,324 RPM | Fan 2: 1,297 RPM', help: 'Fan speed readings and status.', metrics: [
    { label: 'Fan 1', value: '1,324 RPM', status: 'OK', icon: 'fan', history: true }, { label: 'Fan 2', value: '1,297 RPM', status: 'OK', icon: 'fan', history: true }, { label: 'Minimum', value: '1,100 RPM', status: 'OK', icon: 'fan' },
  ] },
  { key: 'battery', title: 'Battery', subtitle: 'Health', status: 'OK', summary: 'Health: Normal | Maximum capacity: 94% | Cycle count: 121', help: 'Battery condition and charging information.', metrics: [
    { label: 'Condition', value: 'Normal', status: 'OK', icon: 'battery' }, { label: 'Maximum capacity', value: '94%', status: 'OK', icon: 'battery', history: true }, { label: 'Cycle count', value: '121', status: 'OK', icon: 'battery' }, { label: 'Charging', value: 'No', status: 'OK', icon: 'power' },
  ] },
  { key: 'ssd', title: 'SSD', subtitle: 'Health', status: 'OK', summary: 'SMART: Verified | TRIM: Yes | Free space: 63%', help: 'Internal solid-state storage health.', metrics: [
    { label: 'SMART status', value: 'Verified', status: 'OK' }, { label: 'TRIM support', value: 'Yes', status: 'OK' }, { label: 'Percentage used', value: '7%', status: 'OK', history: true }, { label: 'Media errors', value: '0', status: 'OK' }, { label: 'Unsafe shutdowns', value: '0', status: 'OK' },
  ] },
  { key: 'display', title: 'Display', subtitle: 'Details', status: 'OK', summary: 'Studio Display | 5120 × 2880 | 60 Hz', help: 'Connected display inventory and properties (resolution, refresh, transport).', table: { kind: 'display', headers: ['Name', 'Resolution', 'Mirror', 'Connection', 'Refresh', 'Transport'], rows: [['Studio Display', '5120 × 2880', 'No', 'Thunderbolt', '60 Hz', 'DisplayPort']] } },
  { key: 'network', title: 'Network', subtitle: 'Quality', status: 'OK', summary: 'IPv4: 192.168.x.x | Wi-Fi: Excellent | DNS: Reachable', help: 'Network interfaces and connection quality.', metrics: [
    { label: 'Interface', value: 'Wi-Fi (en0)', status: 'OK', icon: 'wifi' }, { label: 'Signal', value: 'Excellent', status: 'OK', icon: 'wifi' }, { label: 'Wi-Fi RSSI', value: '-52 dBm', status: 'OK', icon: 'wifi', history: true }, { label: 'IPv4', value: '192.168.x.x', status: 'OK' }, { label: 'DNS', value: 'Reachable', status: 'OK' },
  ] },
  { key: 'devices', title: 'Devices', subtitle: 'Connected', status: 'OK', summary: '5 connected', help: 'Connected USB device list (best-effort).', table: { kind: 'devices', headers: ['Bus', 'Device'], rows: [
    ['USB', 'External SSD'], ['USB', 'USB Receiver'], ['Thunderbolt', 'Studio Display'], ['Bluetooth', 'Magic Keyboard'], ['Bluetooth', 'Magic Trackpad'],
  ] } },
  { key: 'ports', title: 'Ports', subtitle: 'USB Ports', status: 'OK', summary: '7 nodes', help: 'USB topology tree and attached devices. Useful for debugging hubs and display alt-mode paths.', table: { kind: 'ports', headers: ['USB'], rows: [
    ['USB 3.1 Bus'], ['  External SSD'], ['    Storage Interface'], ['  USB Receiver'], ['USB 2.0 Bus'], ['  Studio Display Hub'], ['    Display Alt Mode'],
  ] } },
  { key: 'input', title: 'Input', subtitle: 'Keyboards / Mice', status: 'OK', summary: 'Magic Keyboard  •  Magic Trackpad', help: 'Detected keyboards, mice, and related HID devices.', table: { kind: 'input', headers: ['Type', 'Device', 'Transport'], rows: [['Keyboard', 'Magic Keyboard', 'Bluetooth'], ['Trackpad', 'Magic Trackpad', 'Bluetooth']] } },
];

const overview = { key: 'overview', title: 'Overview', subtitle: 'Health alerts' };

export default function Home() {
  const [selectedKey, setSelectedKey] = useState('overview');
  const [query, setQuery] = useState('');
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarVisible, setSidebarVisible] = useState(true);
  const [hiddenKeys, setHiddenKeys] = useState<Set<string>>(new Set());
  const [refreshTick, setRefreshTick] = useState(0);
  const [refreshing, setRefreshing] = useState(false);
  const [unit, setUnit] = useState<'C' | 'F'>('C');
  const contentRef = useRef<HTMLElement>(null);
  const selected = sections.find((section) => section.key === selectedKey);
  const visible = sections.filter((section) => !hiddenKeys.has(section.key));
  const navItems = [overview, ...visible].filter((section) => `${section.title} ${section.subtitle}`.toLowerCase().includes(query.trim().toLowerCase()));
  const density = useContentDensity(contentRef, selectedKey, visible.length);

  useEffect(() => {
    if (window.localStorage.getItem('mhc_temperature_unit') === 'F') window.queueMicrotask(() => setUnit('F'));
    const compactLayout = window.matchMedia('(max-width: 760px)');
    const syncSidebarToLayout = () => setSidebarVisible(!compactLayout.matches);
    window.queueMicrotask(syncSidebarToLayout);
    const timer = window.setInterval(() => setRefreshTick((value) => value + 1), 10_000);
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'r') { event.preventDefault(); triggerRefresh(setRefreshing, setRefreshTick); }
      if (event.key === 'Escape') setSettingsOpen(false);
    };
    compactLayout.addEventListener('change', syncSidebarToLayout);
    window.addEventListener('keydown', onKey);
    return () => { window.clearInterval(timer); compactLayout.removeEventListener('change', syncSidebarToLayout); window.removeEventListener('keydown', onKey); };
  }, []);

  function toggleUnit() {
    setUnit((current) => { const next = current === 'C' ? 'F' : 'C'; window.localStorage.setItem('mhc_temperature_unit', next); return next; });
  }
  function setSectionVisible(key: string, isVisible: boolean) {
    setHiddenKeys((current) => { const next = new Set(current); if (isVisible) next.delete(key); else next.add(key); return next; });
    if (!isVisible && selectedKey === key) setSelectedKey('overview');
  }
  function navigateToSection(key: string) {
    setSelectedKey(key);
    if (window.matchMedia('(max-width: 760px)').matches) setSidebarVisible(false);
  }

  return <main className={`app-shell ${sidebarVisible ? '' : 'sidebar-hidden'}`} aria-label="Mac Health Checkup Demo Mode">
    <header className="titlebar">
      <div className="titlebar-sidebar"><span className="traffic-lights" aria-hidden="true"><i /><i /><i /></span><button className="sidebar-toggle" type="button" onClick={() => setSidebarVisible((value) => !value)} aria-label={`${sidebarVisible ? 'Hide' : 'Show'} sidebar`}><span /><span /></button></div>
      <div className="titlebar-main"><strong>Mac Health Checkup</strong><span className="demo-badge">DEMO MODE</span><span className="titlebar-spacer" /><button className="refresh-tool has-tooltip" type="button" onClick={() => triggerRefresh(setRefreshing, setRefreshTick)} disabled={refreshing} aria-label="Refresh health data" data-tooltip="Refresh health data (Command-R)">{refreshing ? '•••' : '↻'}</button><button className="gear-tool has-tooltip" type="button" onClick={() => setSettingsOpen(true)} aria-label="Settings" data-tooltip="Open settings">⚙︎</button></div>
    </header>
    <div className="split-view">
      <aside className="sidebar" aria-label="Diagnostic sections"><label className="search-field"><span aria-hidden="true">⌕</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search" aria-label="Search" /></label><nav>{navItems.map((section) => {
        const health = section.key === 'overview' ? null : sections.find((item) => item.key === section.key)?.status;
        return <button key={section.key} type="button" className={selectedKey === section.key ? 'selected' : ''} onClick={() => navigateToSection(section.key)} aria-current={selectedKey === section.key ? 'page' : undefined}><span className="sidebar-copy"><strong>{section.title}</strong><small>{section.subtitle}</small></span>{health && <HealthBadge health={health} compact />}</button>;
      })}</nav>{navItems.length === 0 && <p className="empty-search">No Results</p>}</aside>
      <section ref={contentRef} className={`content-pane view-${selectedKey === 'overview' ? 'overview' : 'detail'} density-${density} ${refreshing ? 'refreshing' : ''}`} aria-live="polite">{selectedKey === 'overview' ? <OverviewView sections={visible} onSelect={navigateToSection} refreshTick={refreshTick} unit={unit} toggleUnit={toggleUnit} /> : selected && <SectionDetail section={selected} onBack={() => navigateToSection('overview')} refreshTick={refreshTick} unit={unit} toggleUnit={toggleUnit} />}</section>
    </div>
    {settingsOpen && <SettingsSheet hiddenKeys={hiddenKeys} close={() => setSettingsOpen(false)} reset={() => setHiddenKeys(new Set())} setSectionVisible={setSectionVisible} />}
    <TooltipLayer />
  </main>;
}

function useContentDensity(contentRef: React.RefObject<HTMLElement | null>, selectedKey: string, visibleCount: number): Density {
  const [density, setDensity] = useState<Density>('full');
  useLayoutEffect(() => {
    const pane = contentRef.current; if (!pane) return;
    let firstFrame = 0; let secondFrame = 0; let cancelled = false;
    const needsScroll = () => {
      const scroller = pane.querySelector<HTMLElement>('.overview-scroll, .detail-scroll'); if (!scroller) return false;
      const allowance = selectedKey === 'overview' ? scroller.clientHeight * 1.18 : scroller.clientHeight;
      const pageOverflows = scroller.scrollHeight > allowance + 2;
      const nestedOverflows = [...pane.querySelectorAll<HTMLElement>('.table-scroll')].some((element) => element.scrollHeight > element.clientHeight + 2);
      return pageOverflows || nestedOverflows;
    };
    const fit = () => {
      window.cancelAnimationFrame(firstFrame); window.cancelAnimationFrame(secondFrame);
      setDensity('full');
      firstFrame = window.requestAnimationFrame(() => {
        if (cancelled || !needsScroll()) return;
        setDensity('compact');
        if (selectedKey === 'overview') return;
        secondFrame = window.requestAnimationFrame(() => { if (!cancelled && needsScroll()) setDensity('tight'); });
      });
    };
    const observer = new ResizeObserver(fit); observer.observe(pane); fit();
    return () => { cancelled = true; observer.disconnect(); window.cancelAnimationFrame(firstFrame); window.cancelAnimationFrame(secondFrame); };
  }, [contentRef, selectedKey, visibleCount]);
  return density;
}

function TooltipLayer() {
  const [tooltip, setTooltip] = useState<{ target: HTMLElement; text: string } | null>(null);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const tooltipRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const findTarget = (value: EventTarget | null) => value instanceof Element ? value.closest<HTMLElement>('[data-tooltip]') : null;
    const show = (target: HTMLElement | null) => {
      const text = target?.dataset.tooltip?.trim();
      if (!target || !text) { setTooltip(null); return; }
      setTooltip((current) => current?.target === target && current.text === text ? current : { target, text });
    };
    const onPointerOver = (event: PointerEvent) => show(findTarget(event.target));
    const onPointerOut = (event: PointerEvent) => { const next = findTarget(event.relatedTarget); if (next !== findTarget(event.target)) show(next); };
    const onFocusIn = (event: FocusEvent) => show(findTarget(event.target));
    const onFocusOut = (event: FocusEvent) => { const next = findTarget(event.relatedTarget); if (next !== findTarget(event.target)) show(next); };
    const hide = () => setTooltip(null);
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') hide(); };
    document.addEventListener('pointerover', onPointerOver); document.addEventListener('pointerout', onPointerOut); document.addEventListener('focusin', onFocusIn); document.addEventListener('focusout', onFocusOut); document.addEventListener('keydown', onKeyDown); window.addEventListener('scroll', hide, true); window.addEventListener('resize', hide);
    return () => { document.removeEventListener('pointerover', onPointerOver); document.removeEventListener('pointerout', onPointerOut); document.removeEventListener('focusin', onFocusIn); document.removeEventListener('focusout', onFocusOut); document.removeEventListener('keydown', onKeyDown); window.removeEventListener('scroll', hide, true); window.removeEventListener('resize', hide); };
  }, []);

  useLayoutEffect(() => {
    const bubble = tooltipRef.current; if (!tooltip || !bubble) return;
    const gap = 10; const margin = 12; const target = tooltip.target.getBoundingClientRect(); const bubbleRect = bubble.getBoundingClientRect();
    const clamp = (value: number, min: number, max: number) => Math.min(Math.max(value, min), Math.max(min, max));
    let top: number; let left: number;
    if (window.innerHeight - target.bottom - gap >= bubbleRect.height) { top = target.bottom + gap; left = clamp(target.left + (target.width - bubbleRect.width) / 2, margin, window.innerWidth - bubbleRect.width - margin); }
    else if (target.top - gap >= bubbleRect.height) { top = target.top - bubbleRect.height - gap; left = clamp(target.left + (target.width - bubbleRect.width) / 2, margin, window.innerWidth - bubbleRect.width - margin); }
    else if (window.innerWidth - target.right - gap >= bubbleRect.width) { left = target.right + gap; top = clamp(target.top + (target.height - bubbleRect.height) / 2, margin, window.innerHeight - bubbleRect.height - margin); }
    else { left = target.left - bubbleRect.width - gap; top = clamp(target.top + (target.height - bubbleRect.height) / 2, margin, window.innerHeight - bubbleRect.height - margin); }
    setPosition({ top, left });
    const previous = tooltip.target.getAttribute('aria-describedby'); tooltip.target.setAttribute('aria-describedby', 'context-tooltip');
    return () => { if (previous) tooltip.target.setAttribute('aria-describedby', previous); else tooltip.target.removeAttribute('aria-describedby'); };
  }, [tooltip]);

  if (!tooltip) return null;
  return createPortal(<div ref={tooltipRef} id="context-tooltip" className="app-tooltip" role="tooltip" style={position}>{tooltip.text}</div>, document.body);
}

function triggerRefresh(setRefreshing: (value: boolean) => void, setRefreshTick: React.Dispatch<React.SetStateAction<number>>) { setRefreshing(true); window.setTimeout(() => { setRefreshTick((value) => value + 1); setRefreshing(false); }, 650); }
function HealthBadge({ health, compact = false }: { health: Health; compact?: boolean }) { const explanation = healthExplanation(health); return <span className={`health-badge has-tooltip ${health.toLowerCase()} ${compact ? 'compact' : ''}`} data-tooltip={explanation} tabIndex={0}>{health}</span>; }

function OverviewView({ sections: visible, onSelect, refreshTick, unit, toggleUnit }: { sections: Section[]; onSelect: (key: string) => void; refreshTick: number; unit: 'C' | 'F'; toggleUnit: () => void }) {
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const priority: Record<Health, number> = { BAD: 0, WARN: 1, UNK: 2, OK: 3 };
  const ordered = visible.filter((section) => section.status === 'WARN' || section.status === 'BAD').map((section) => { const metrics = section.metrics?.filter((metric) => metric.status === 'WARN' || metric.status === 'BAD'); return metrics?.length ? { ...section, metrics, field: undefined, table: undefined, summary: metrics.map((metric) => `${metric.label}: ${metric.value}`).join(' | ') } : { ...section, metrics: undefined }; }).sort((a, b) => priority[a.status] - priority[b.status]);
  return <div className="overview-scroll"><div className="overview-stack">{ordered.length === 0 && <article className="card"><h2>No warnings or critical alerts</h2><p>No alerts in the visible sections. Choose a section in the sidebar for all readings, or review visibility settings.</p></article>}{ordered.map((section) => {
    const isExpanded = expanded.has(section.key); const hasExpandable = Boolean((section.field && (section.field.length > 160 || section.field.includes('\n'))) || (section.metrics && section.metrics.length > 1) || section.table?.rows.length); const firstHistory = section.metrics?.find((metric) => metric.history); const firstSeries = firstHistory ? seriesFor(section.key, firstHistory.label, firstHistory.value, refreshTick) : [];
    return <article className="card overview-card has-tooltip" key={section.key} onClick={() => onSelect(section.key)} onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onSelect(section.key); } }} role="button" tabIndex={0} data-tooltip={section.help}><div className="overview-heading"><div className="section-heading"><h2>{section.title}</h2><p>{section.subtitle}</p></div><span className="heading-spacer" />{firstHistory && firstSeries.length >= 3 && <Sparkline values={firstSeries} label={`${section.title} ${firstHistory.label} history`} />}{hasExpandable && <button type="button" className="disclosure has-tooltip" aria-label={`${isExpanded ? 'Collapse' : 'Expand'} ${section.title}`} aria-expanded={isExpanded} data-tooltip={`${isExpanded ? 'Collapse' : 'Expand'} the ${section.title} preview`} onClick={(event) => { event.stopPropagation(); setExpanded((current) => { const next = new Set(current); if (next.has(section.key)) next.delete(section.key); else next.add(section.key); return next; }); }}>{isExpanded ? '⌄' : '›'}</button>}<HealthBadge health={section.status} /></div>{isExpanded ? <OverviewExpanded section={section} refreshTick={refreshTick} unit={unit} toggleUnit={toggleUnit} /> : <p className="overview-summary">{formatTemperatureText(section.summary, unit)}</p>}</article>;
  })}</div></div>;
}

function OverviewExpanded({ section, refreshTick, unit, toggleUnit }: { section: Section; refreshTick: number; unit: 'C' | 'F'; toggleUnit: () => void }) {
  return <div className="overview-expanded" onClick={(event) => event.stopPropagation()}>{section.field && <p className="expanded-field">{formatTemperatureText(section.field, unit)}</p>}{section.metrics && <MetricList section={section} metrics={section.metrics.slice(0, 6)} refreshTick={refreshTick} unit={unit} toggleUnit={toggleUnit} showHistory={false} />}{section.table && section.table.rows.length > 0 && <TablePreview table={section.table} />}</div>;
}

function SectionDetail({ section, onBack, refreshTick, unit, toggleUnit }: { section: Section; onBack: () => void; refreshTick: number; unit: 'C' | 'F'; toggleUnit: () => void }) {
  const showField = Boolean(section.field && ((!section.metrics && !section.table) || ['performance', 'general', 'processes', 'startup', 'backups'].includes(section.key)));
  return <div className="detail-scroll"><div className="detail-stack"><header className="detail-heading"><button className="has-tooltip" type="button" onClick={onBack} data-tooltip="Return to health alerts">‹&nbsp; Overview</button><div className="section-heading has-tooltip" data-tooltip={section.help} tabIndex={0}><h2>{section.title}</h2><p>{section.subtitle}</p></div><span /><HealthBadge health={section.status} /></header>{showField && (section.key === 'general' ? <GeneralInfoCard field={section.field!} /> : <article className="card field-card has-tooltip" data-tooltip={section.help} tabIndex={0}>{formatTemperatureText(section.field!, unit)}</article>)}{section.metrics && <article className="card metrics-card"><h3>Metrics</h3><MetricList section={section} metrics={section.metrics} refreshTick={refreshTick} unit={unit} toggleUnit={toggleUnit} showHistory /></article>}{section.table && <SectionTable section={section} table={section.table} />}</div></div>;
}

function MetricList({ section, metrics, refreshTick, unit, toggleUnit, showHistory }: { section: Section; metrics: Metric[]; refreshTick: number; unit: 'C' | 'F'; toggleUnit: () => void; showHistory: boolean }) {
  const hasHistoryColumn = showHistory && metrics.some((metric) => metric.history);
  return <div className={`metric-list ${hasHistoryColumn ? 'has-history' : 'no-history'}`}>{section.key === 'performance' && <div className="performance-columns"><span>Sensor</span><span>Value <button className="has-tooltip" type="button" onClick={toggleUnit} data-tooltip="Toggle between Celsius and Fahrenheit">°{unit}</button></span></div>}{metrics.map((metric) => { const explanation = metricExplanation(section, metric); return <div className="metric-row has-tooltip" key={metric.label} data-tooltip={explanation} tabIndex={0}><span className={`metric-symbol ${metric.icon ? '' : 'empty'}`} aria-hidden="true">{metric.icon ? iconFor(metric.icon) : ''}</span><span className="metric-label">{metric.label}</span><TemperatureValue raw={metric.value} unit={unit} toggleUnit={toggleUnit} health={metric.status} />{hasHistoryColumn && (metric.history ? <Sparkline values={seriesFor(section.key, metric.label, metric.value, refreshTick)} label={`${section.title} ${metric.label} history`} /> : <span className="sparkline-space" />)}<HealthBadge health={metric.status} /></div>; })}</div>;
}

function TemperatureValue({ raw, unit, toggleUnit, health }: { raw: string; unit: 'C' | 'F'; toggleUnit: () => void; health: Health }) {
  const match = raw.match(/^(-?\d+(?:\.\d+)?)\s*°?\s*([CF])$/i); if (!match) return <strong className={`metric-value ${health.toLowerCase()}`}>{raw}</strong>;
  const source = Number(match[1]); const sourceUnit = match[2].toUpperCase(); const converted = sourceUnit === unit ? source : unit === 'F' ? source * 9 / 5 + 32 : (source - 32) * 5 / 9; const formatted = Number.isInteger(source) ? Math.round(converted).toString() : converted.toFixed(1);
  return <strong className={`metric-value temperature ${health.toLowerCase()}`}>{formatted}<button className="has-tooltip" type="button" onClick={toggleUnit} data-tooltip="Toggle between Celsius and Fahrenheit">°{unit}</button></strong>;
}

function Sparkline({ values, label }: { values: number[]; label: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => { const canvas = ref.current; if (!canvas) return; const draw = () => { const width = Math.max(1, canvas.clientWidth); const height = Math.max(1, canvas.clientHeight); const ratio = window.devicePixelRatio || 1; canvas.width = Math.round(width * ratio); canvas.height = Math.round(height * ratio); const context = canvas.getContext('2d'); if (!context) return; context.setTransform(ratio, 0, 0, ratio, 0, 0); context.clearRect(0, 0, width, height); const low = Math.min(...values); const high = Math.max(...values); const span = Math.max(0.000001, high - low); context.beginPath(); values.forEach((value, index) => { const x = index / Math.max(1, values.length - 1) * width; const y = height - ((value - low) / span * height); if (index === 0) context.moveTo(x, y); else context.lineTo(x, y); }); context.strokeStyle = 'rgba(88,166,255,.85)'; context.lineWidth = 1.6; context.lineJoin = 'round'; context.stroke(); }; draw(); const observer = new ResizeObserver(draw); observer.observe(canvas); return () => observer.disconnect(); }, [values]);
  const explanation = `${label}. This synthetic trend shows recent movement over time; it does not read data from your computer.`;
  return <span className="sparkline-wrap has-tooltip" data-tooltip={explanation} tabIndex={0}><canvas ref={ref} className="sparkline" role="img" aria-label={explanation} /></span>;
}

function GeneralInfoCard({ field }: { field: string }) {
  const parts = field.split('|').map((part) => part.trim()); const rows = [['laptop', 'Model', parts[0] ?? 'Mac'], ['cpu', 'Chip', parts[1] ?? 'Apple silicon'], ['window', 'OS', parts[2] ?? 'macOS'], ['number', 'Serial', parts[3] ?? 'DEMO-SERIAL']];
  return <article className="card general-card">{rows.map(([icon, label, value], index) => { const explanation = generalExplanation(label); return <div className="general-row has-tooltip" key={label} data-tooltip={explanation} tabIndex={0}><span className="general-symbol" aria-hidden="true">{iconFor(icon)}</span><span>{label}</span><strong className={label === 'OS' || label === 'Serial' ? 'mono' : ''}>{value}</strong>{index < rows.length - 1 && <i />}</div>; })}</article>;
}

function SectionTable({ section, table }: { section: Section; table: NonNullable<Section['table']> }) {
  if (table.kind === 'display') return <article className="card native-list">{table.rows.map((row, index) => <div className="native-list-row has-tooltip" key={index} data-tooltip="Shows the display’s resolution, refresh rate, connection, and transport. Healthy: the expected native resolution and stable refresh rate." tabIndex={0}><span className="list-symbol">{iconFor('display')}</span><span><strong>{row[0]}</strong><small>{[row[1], row[4], row[3], row[5]].filter(Boolean).join('  •  ')}</small></span></div>)}</article>;
  if (table.kind === 'input') return <article className="card native-list">{table.rows.map((row, index) => <div className="native-list-row input-row has-tooltip" key={index} data-tooltip="A detected input device and its connection type. Healthy: recognized, responsive, and connected through the expected transport." tabIndex={0}><span className="list-symbol">{iconFor(row[0].toLowerCase())}</span><span><strong>{row[1]}</strong><small>{row[0]}</small></span><em>{row[2]}</em></div>)}</article>;
  if (table.kind === 'devices') return <DevicesTable rows={table.rows} />;
  if (table.kind === 'ports') return <PortsTree rows={table.rows} />;
  return <article className={`card table-card ${section.key}`}><h3>{table.title ?? 'Table'}</h3><div className="table-scroll"><table><thead><tr>{table.headers.map((header) => { const explanation = tableColumnExplanation(header); return <th className="has-tooltip" key={header} data-tooltip={explanation} tabIndex={0}>{header}</th>; })}</tr></thead><tbody>{table.rows.map((row, rowIndex) => <tr key={rowIndex}>{table.headers.map((header, columnIndex) => { const value = row[columnIndex] ?? ''; return <td className="has-tooltip" key={columnIndex} data-tooltip={tableColumnExplanation(header)} tabIndex={0}>{value}</td>; })}</tr>)}</tbody></table></div></article>;
}

function DevicesTable({ rows }: { rows: string[][] }) {
  const busOrder = ['USB', 'Thunderbolt', 'Bluetooth', 'Network']; const buses = [...new Set(rows.map((row) => row[0]))].sort((a, b) => (busOrder.indexOf(a) < 0 ? 99 : busOrder.indexOf(a)) - (busOrder.indexOf(b) < 0 ? 99 : busOrder.indexOf(b)));
  return <article className="card devices-card">{buses.map((bus) => <section key={bus}><header className="has-tooltip" data-tooltip="Groups devices that share this connection type." tabIndex={0}><span>{iconFor(bus.toLowerCase())}</span><small>{bus}</small></header>{rows.filter((row) => row[0] === bus).map((row, index) => <div className="has-tooltip" key={index} data-tooltip="A synthetic connected-device record. Healthy: detected on the expected bus without repeated disconnects." tabIndex={0}><span>{iconFor(row[1].toLowerCase())}</span><strong>{row[1]}</strong></div>)}</section>)}</article>;
}

type TreeNode = { label: string; children: TreeNode[]; id: string };
function buildTree(rows: string[][]) { const roots: TreeNode[] = []; const stack: TreeNode[] = []; rows.forEach((row, index) => { const raw = row[0] ?? ''; const depth = Math.floor((raw.match(/^ */)?.[0].length ?? 0) / 2); const node = { label: raw.trim(), children: [], id: `${depth}-${index}-${raw.trim()}` }; while (stack.length > depth) stack.pop(); if (stack.length) stack[stack.length - 1].children.push(node); else roots.push(node); stack.push(node); }); return roots; }
function PortsTree({ rows }: { rows: string[][] }) { return <article className="card ports-card"><h3>USB</h3><div className="tree"><TreeNodes nodes={buildTree(rows)} depth={0} /></div></article>; }
function TreeNodes({ nodes, depth }: { nodes: TreeNode[]; depth: number }) { return <>{nodes.map((node) => { const explanation = node.children.length ? 'A connection branch containing attached USB devices. Healthy: expected children appear and remain connected.' : 'An attached endpoint in the USB tree. Healthy: detected under the expected parent without disconnects.'; return node.children.length ? <details key={node.id} open><summary className="has-tooltip" data-tooltip={explanation} style={{ paddingLeft: depth * 18 }}><span>{iconFor(node.label.toLowerCase())}</span><strong>{node.label}</strong></summary><TreeNodes nodes={node.children} depth={depth + 1} /></details> : <div className="tree-leaf has-tooltip" key={node.id} data-tooltip={explanation} tabIndex={0} style={{ paddingLeft: 18 + depth * 18 }}><span>{iconFor(node.label.toLowerCase())}</span>{node.label}</div>; })}</>; }

function TablePreview({ table }: { table: NonNullable<Section['table']> }) { const columns = table.headers.slice(0, 3); return <div className="table-preview"><div className="preview-row preview-header">{columns.map((header) => <span key={header}>{header}</span>)}</div>{table.rows.slice(0, 4).map((row, rowIndex) => <div className="preview-row" key={rowIndex}>{columns.map((_, index) => <span key={index}>{row[index] ?? ''}</span>)}</div>)}{table.rows.length > 4 && <small>… {table.rows.length - 4} more rows</small>}</div>; }

function SettingsSheet({ hiddenKeys, close, reset, setSectionVisible }: { hiddenKeys: Set<string>; close: () => void; reset: () => void; setSectionVisible: (key: string, visible: boolean) => void }) {
  return <div className="sheet-backdrop" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) close(); }}><section className="settings-sheet" role="dialog" aria-modal="true" aria-labelledby="settings-title"><div className="settings-stack"><article className="card settings-intro"><header><button type="button" onClick={close}>Done</button><div><h2 id="settings-title">Settings</h2><small>Customize sections</small></div><span /><button className="reset-button" type="button" onClick={reset}>Reset</button></header><p>Show or hide sections in the sidebar and overview. Demo Mode uses fictional data and does not inspect your Mac. Refresh updates the simulated readings.</p></article><article className="card visibility-card">{sections.map((section, index) => <label key={section.key}><span><strong>{section.title}</strong><small>{section.subtitle}</small></span><input type="checkbox" checked={!hiddenKeys.has(section.key)} onChange={(event) => setSectionVisible(section.key, event.target.checked)} aria-label={`${section.title} visibility`} /><i aria-hidden="true" />{index < sections.length - 1 && <b />}</label>)}</article></div></section></div>;
}

function iconFor(kind: string) { const value = kind.toLowerCase(); if (value.includes('keyboard')) return '▤'; if (value.includes('mouse') || value.includes('trackpad') || value.includes('digitizer')) return '▯'; if (value.includes('display') || value === 'window') return '▱'; if (value === 'laptop') return '▰'; if (value.includes('cpu')) return '▣'; if (value.includes('gpu')) return '▧'; if (value.includes('number')) return '#'; if (value.includes('fan')) return '✣'; if (value.includes('battery')) return '▥'; if (value.includes('wifi') || value.includes('network') || value.includes('ethernet')) return '◎'; if (value.includes('thunderbolt') || value.includes('power')) return 'ϟ'; if (value.includes('bluetooth')) return 'ᛒ'; if (value.includes('usb') || value.includes('hub') || value.includes('receiver')) return '⚯'; if (value.includes('thermometer')) return '♨'; return '◉'; }
function healthExplanation(health: Health) { return ({ OK: 'OK means this reading is within the expected healthy range.', WARN: 'WARN means this item deserves attention but is not an immediate failure.', BAD: 'BAD means this check found a condition that should be addressed.', UNK: 'UNK means the app could not reliably read this value.' } as const)[health]; }
function metricExplanation(section: Section, metric: Metric) {
  const key = metric.label.toLowerCase();
  const descriptions: Record<string, string> = {
    'cpu temperature': 'Current processor temperature; sustained high heat can reduce performance.', 'gpu temperature': 'Current graphics processor temperature.', 'cpu utilization': 'The percentage of processor capacity currently in use.', 'load average': 'Average amount of runnable work waiting for processor time.', 'thermal pressure': 'macOS summary of whether heat is limiting system performance.', 'filevault': 'Full-disk encryption that protects data when the Mac is powered off.', 'sip': 'System Integrity Protection prevents unauthorized changes to protected macOS files.', 'gatekeeper': 'Checks downloaded apps for trusted signing and notarization.', 'firewall': 'Controls unsolicited incoming network connections.', 'disk free': 'Available storage remaining on the startup disk.', 'memory free': 'Memory currently available for applications and macOS.', 'configured': 'Whether Time Machine has a backup destination configured.', 'last backup': 'When Time Machine most recently completed a backup.', 'destination': 'The disk or location receiving Time Machine backups.', 'automatic backups': 'Whether macOS is scheduling backups automatically.', 'current version': 'The macOS version currently installed.', 'available update': 'A newer macOS update that can be installed.', 'automatic checks': 'Whether macOS periodically checks for software updates.', 'power source': 'Whether the Mac is using an adapter or battery power.', 'thermal state': 'macOS summary of current heat-related operating limits.', 'condition': 'macOS assessment of overall battery health.', 'maximum capacity': 'Battery capacity remaining compared with when it was new.', 'cycle count': 'Number of complete charge-cycle equivalents used by the battery.', 'charging': 'Whether the battery is currently receiving charge.', 'smart status': 'Drive self-diagnostic result for likely hardware failure.', 'trim support': 'Whether deleted SSD blocks are reclaimed efficiently.', 'percentage used': 'Estimated portion of the SSD write-life already consumed.', 'media errors': 'Permanent drive read or write errors reported by storage health data.', 'unsafe shutdowns': 'Shutdowns where the drive lost power without a normal sequence.', 'interface': 'Network adapter currently used for the connection.', 'signal': 'Plain-language assessment of wireless connection strength.', 'wi-fi rssi': 'Raw Wi-Fi signal strength; values closer to zero are stronger.', 'ipv4': 'Local network address assigned to this Mac.', 'dns': 'Whether domain-name lookup services can be reached.'
  };
  const description = descriptions[key] ?? (key.startsWith('fan ') ? 'Current cooling-fan speed in revolutions per minute.' : key === 'minimum' ? 'Lowest expected cooling-fan speed.' : `A ${section.title.toLowerCase()} health reading.`);
  const healthyTargets: Record<string, string> = {
    'cpu temperature': 'generally below 85 °C during sustained work', 'gpu temperature': 'generally below 90 °C during sustained work', 'cpu utilization': 'brief peaks are normal; investigate only if it stays near 100%', 'load average': 'sustained load should remain below the Mac’s available CPU-core count', 'thermal pressure': 'Nominal', 'filevault': 'On', 'sip': 'Enabled', 'gatekeeper': 'Enabled', 'firewall': 'Enabled', 'disk free': 'keep roughly 15–20% or more available', 'memory free': 'some fluctuation is normal; avoid sustained memory pressure or swapping', 'configured': 'Yes', 'last backup': 'a successful backup within the last 24 hours', 'destination': 'available and writable', 'automatic backups': 'On', 'current version': 'the latest supported release for this Mac', 'available update': 'none pending after important updates are installed', 'automatic checks': 'On', 'power source': 'the expected source for the current situation', 'thermal state': 'Nominal', 'condition': 'Normal', 'maximum capacity': '80% or higher', 'cycle count': 'below the battery’s rated cycle limit', 'charging': 'matches whether power is connected and charging is needed', 'smart status': 'Verified', 'trim support': 'Yes', 'percentage used': 'lower is better; well below 80% indicates substantial write life remains', 'media errors': '0', 'unsafe shutdowns': '0 or very few', 'interface': 'the expected active adapter', 'signal': 'Good or Excellent', 'wi-fi rssi': 'about −67 dBm or better for a reliable connection', 'ipv4': 'a valid address from the current network', 'dns': 'Reachable'
  };
  const healthyTarget = healthyTargets[key] ?? (key.startsWith('fan ') || key === 'minimum' ? 'stable and automatically controlled without warnings' : 'within the normal range reported by macOS');
  return `${description} Healthy: ${healthyTarget}.`;
}
function tableColumnExplanation(header: string) { const explanations: Record<string, string> = { Type: 'Classification used to group this item.', PID: 'Process identifier assigned by macOS.', 'CPU%': 'Approximate percentage of processor capacity used by the process.', 'MEM%': 'Approximate percentage of system memory used by the process.', Command: 'Name of the running process or executable.', Label: 'Readable name or launch-service identifier.', State: 'Whether the item is enabled or currently loaded.', Path: 'Filesystem location of the app, launch agent, or daemon.' }; return explanations[header] ?? `Values reported for ${header}.`; }
function generalExplanation(label: string) { const descriptions: Record<string, string> = { Model: 'Identifies the Mac hardware model so other readings can be interpreted correctly.', Chip: 'Identifies the processor family and expected capabilities.', OS: 'Shows the installed macOS release. Healthy: a currently supported version with important updates installed.', Serial: 'A synthetic identifier in Demo Mode; the downloaded app reads the real serial number locally.' }; return descriptions[label] ?? 'Basic machine information used to interpret the health report.'; }
function formatTemperatureText(text: string, unit: 'C' | 'F') { if (unit === 'C') return text; return text.replace(/(-?\d+(?:\.\d+)?)\s*°\s*C/g, (_, raw) => `${Math.round(Number(raw) * 9 / 5 + 32)} °F`); }
function seriesFor(sectionKey: string, label: string, rawValue: string, tick: number) { const match = rawValue.replaceAll(',', '').match(/-?\d+(?:\.\d+)?/); if (!match) return []; const base = Number(match[0]); if (!Number.isFinite(base)) return []; let seed = 0; for (const char of `${sectionKey}:${label}`) seed = (seed * 31 + char.charCodeAt(0)) >>> 0; const amplitude = Math.max(Math.abs(base) * 0.045, 0.7); return Array.from({ length: 30 }, (_, index) => base + Math.sin((index + tick + seed % 13) * .67) * amplitude + Math.cos((index + seed % 7) * .31) * amplitude * .32); }

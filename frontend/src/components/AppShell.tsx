import { ReactNode } from 'react';
import { AppShell as MantineAppShell, NavLink, Group, Select, SegmentedControl, Text, Button } from '@mantine/core';
import { MonthPickerInput } from '@mantine/dates';
import { NavLink as RouterNavLink, useNavigate } from 'react-router-dom';
import dayjs from 'dayjs';
import { useSeleccion, Rol } from '../context/SeleccionContext';
import { useClientes } from '../api/hooks';
import { useAuth } from '../auth/AuthContext';

const LINKS = [
  { to: '/clientes', label: 'Clientes' },
  { to: '/subida', label: 'Subida XML' },
  { to: '/resumen', label: 'Resumen' },
  { to: '/d150', label: 'D-150' },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { clienteId, periodo, rol, setClienteId, setPeriodo, setRol } = useSeleccion();
  const { data: clientes } = useClientes();
  const { logout } = useAuth();
  const navigate = useNavigate();

  return (
    <MantineAppShell header={{ height: 60 }} navbar={{ width: 200, breakpoint: 'sm' }} padding="md">
      <MantineAppShell.Header>
        <Group h="100%" px="md" justify="space-between">
          <Text fw={700} c="teal">Sistema XML</Text>
          <Group>
            <Select
              aria-label="Cliente"
              placeholder="Cliente"
              data={(clientes ?? []).map((c) => ({ value: String(c.id), label: c.nombre }))}
              value={clienteId != null ? String(clienteId) : null}
              onChange={(v) => setClienteId(v ? Number(v) : null)}
              w={200}
            />
            <MonthPickerInput
              aria-label="Período"
              placeholder="Período"
              value={periodo ? dayjs(periodo + '-01').toDate() : null}
              onChange={(d: Date | string | null) => setPeriodo(d ? dayjs(d).format('YYYY-MM') : null)}
              w={140}
            />
            <SegmentedControl
              aria-label="Rol"
              value={rol}
              onChange={(v) => setRol(v as Rol)}
              data={[{ value: 'compra', label: 'Compra' }, { value: 'venta', label: 'Venta' }]}
            />
            <Button variant="subtle" onClick={() => { logout(); navigate('/login'); }}>Salir</Button>
          </Group>
        </Group>
      </MantineAppShell.Header>
      <MantineAppShell.Navbar p="xs">
        {LINKS.map((l) => (
          <NavLink key={l.to} component={RouterNavLink} to={l.to} label={l.label} />
        ))}
      </MantineAppShell.Navbar>
      <MantineAppShell.Main>{children}</MantineAppShell.Main>
    </MantineAppShell>
  );
}

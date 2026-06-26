import { useState } from 'react';
import {
  Stack,
  Title,
  Table,
  SegmentedControl,
  Alert,
  Loader,
  Button,
  Text,
} from '@mantine/core';
import { useSeleccion } from '../context/SeleccionContext';
import { useD150 } from '../api/hooks';
import { formatColones } from '../lib/money';

// ---------------------------------------------------------------------------
// Types for the real nested shape returned by motor/d150.py
// ---------------------------------------------------------------------------

interface PorTasaEntry {
  base: string | number;
  iva: string | number;
}

interface SeccionBase {
  por_tasa: Record<string, PorTasaEntry>;
  exentas: string | number;
  no_sujetas: string | number;
  total_gravadas: string | number;
  total_general: string | number;
}

interface SeccionVentas extends SeccionBase {
  total_impuesto: string | number;
}

interface SeccionCompras extends SeccionBase {
  total_credito: string | number;
  no_deducibles?: string | number;
  tiquetes_excluidos_n?: number;
  tiquetes_excluidos_iva?: string | number;
}

interface Liquidacion {
  debito_fiscal: string | number;
  credito_fiscal: string | number;
  impuesto_neto: string | number;
  estado: string;
}

interface D150Shape {
  ventas: SeccionVentas;
  compras: SeccionCompras;
  liquidacion: Liquidacion;
}

// ---------------------------------------------------------------------------
// Rendering helpers
// ---------------------------------------------------------------------------

interface Row {
  label: string;
  value: string | number;
  isMoneda: boolean; // true → format with ₡ in preciso view
}

function buildRows(d: D150Shape, isPreciso: boolean): Row[] {
  const rows: Row[] = [];
  const fmt = (v: string | number) =>
    isPreciso ? formatColones(String(v)) : String(v);
  const fmtInt = (v: string | number) => String(v); // OVI: always plain integer

  const addMoney = (label: string, v: string | number) =>
    rows.push({ label, value: v, isMoneda: true });
  const addPlain = (label: string, v: string | number) =>
    rows.push({ label, value: v, isMoneda: false });

  // --- VENTAS ---
  addPlain('── VENTAS ──', '');
  for (const [pct, entry] of Object.entries(d.ventas.por_tasa)) {
    addMoney(`  Ventas gravadas ${pct} – base`, entry.base);
    addMoney(`  Ventas gravadas ${pct} – IVA`, entry.iva);
  }
  addMoney('  Exentas', d.ventas.exentas);
  addMoney('  No sujetas', d.ventas.no_sujetas);
  addMoney('  Total gravadas', d.ventas.total_gravadas);
  addMoney('  Total general ventas', d.ventas.total_general);
  addMoney('  Total impuesto (débito)', d.ventas.total_impuesto);

  // --- COMPRAS ---
  addPlain('── COMPRAS ──', '');
  for (const [pct, entry] of Object.entries(d.compras.por_tasa)) {
    addMoney(`  Compras gravadas ${pct} – base`, entry.base);
    addMoney(`  Compras gravadas ${pct} – IVA`, entry.iva);
  }
  addMoney('  Exentas', d.compras.exentas);
  addMoney('  No sujetas', d.compras.no_sujetas);
  addMoney('  Total gravadas', d.compras.total_gravadas);
  addMoney('  Total general compras', d.compras.total_general);
  addMoney('  Total crédito fiscal', d.compras.total_credito);
  if (d.compras.no_deducibles !== undefined) {
    addMoney('  No deducibles', d.compras.no_deducibles);
  }
  if (d.compras.tiquetes_excluidos_n !== undefined) {
    addPlain('  Tiquetes excluidos (cant.)', d.compras.tiquetes_excluidos_n);
  }
  if (d.compras.tiquetes_excluidos_iva !== undefined) {
    addMoney('  Tiquetes excluidos (IVA)', d.compras.tiquetes_excluidos_iva);
  }

  // --- LIQUIDACIÓN ---
  addPlain('── LIQUIDACIÓN ──', '');
  addMoney('  Débito fiscal', d.liquidacion.debito_fiscal);
  addMoney('  Crédito fiscal', d.liquidacion.credito_fiscal);
  addMoney('  Impuesto neto', d.liquidacion.impuesto_neto);
  addPlain('  Estado', d.liquidacion.estado);

  return rows;

  // suppress unused warning — fmt/fmtInt are conceptually referenced via isMoneda
  void fmt; void fmtInt;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function D150Page() {
  const { clienteId, periodo } = useSeleccion();
  const { data, isLoading, isError, refetch } = useD150(clienteId, periodo);
  const [vista, setVista] = useState<'preciso' | 'ovi'>('preciso');

  if (clienteId == null || periodo == null) {
    return (
      <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>
    );
  }
  if (isLoading) return <Loader />;
  if (isError) {
    return (
      <Alert color="red">
        Error al cargar el D-150{' '}
        <Button size="xs" onClick={() => refetch()}>
          Reintentar
        </Button>
      </Alert>
    );
  }

  const isPreciso = vista === 'preciso';
  const raw = isPreciso ? data?.preciso : data?.ovi;

  // Safely cast — the shape matches D150Shape when the API works
  const d = raw as unknown as D150Shape | undefined;

  const rows = d ? buildRows(d, isPreciso) : [];

  return (
    <Stack>
      <Title order={2}>D-150</Title>
      <SegmentedControl
        value={vista}
        onChange={(v) => setVista(v as 'preciso' | 'ovi')}
        data={[
          { value: 'preciso', label: 'Preciso' },
          { value: 'ovi', label: 'OVI (entero)' },
        ]}
      />
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Renglón</Table.Th>
            <Table.Th>Monto</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {rows.map((row, i) => {
            const isSectionHeader = row.label.startsWith('──');
            if (isSectionHeader) {
              return (
                <Table.Tr key={i} style={{ background: 'var(--mantine-color-gray-1)' }}>
                  <Table.Td colSpan={2}>
                    <Text fw={700} size="sm">
                      {row.label}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              );
            }
            const displayValue =
              row.value === ''
                ? ''
                : row.isMoneda
                ? isPreciso
                  ? formatColones(String(row.value))
                  : String(row.value)
                : String(row.value);
            return (
              <Table.Tr key={i}>
                <Table.Td>{row.label}</Table.Td>
                <Table.Td>{displayValue}</Table.Td>
              </Table.Tr>
            );
          })}
        </Table.Tbody>
      </Table>
    </Stack>
  );
}

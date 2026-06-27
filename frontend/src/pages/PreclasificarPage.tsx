import { useState } from 'react';
import { Stack, Title, Tabs, Table, Select, TextInput, Button, Group, Alert, Loader, Text } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { useQueryClient } from '@tanstack/react-query';
import { useSeleccion, Rol } from '../context/SeleccionContext';
import { usePreclasificacion, useCrearRegla, PorPreclasificacion, ReglaCreate } from '../api/hooks';
import { formatColones } from '../lib/money';

// Mantener en sync con ReglasPage.tsx — extraer a un módulo de constantes si aparece un tercer consumidor.
const CLASIFICACIONES = ['Compras', 'Gastos', 'Bienes de Capital', 'No Deducibles', 'Sin Clasificar'];

interface Asignacion {
  clasificacion: string;
  sub: string;
}

function Panel({ por, clienteId, periodo, rol }: { por: PorPreclasificacion; clienteId: number; periodo: string; rol: Rol }) {
  const { data, isLoading, isError, refetch } = usePreclasificacion(clienteId, periodo, rol, por);
  const crear = useCrearRegla();
  const qc = useQueryClient();
  const [asig, setAsig] = useState<Record<string, Asignacion>>({});

  function setClas(clave: string, clasificacion: string) {
    setAsig((a) => ({ ...a, [clave]: { clasificacion, sub: a[clave]?.sub ?? '' } }));
  }
  function setSub(clave: string, sub: string) {
    setAsig((a) => ({ ...a, [clave]: { clasificacion: a[clave]?.clasificacion ?? '', sub } }));
  }

  async function guardar() {
    const elegidas = Object.entries(asig).filter(([, v]) => v.clasificacion);
    if (elegidas.length === 0) return;
    const results = await Promise.allSettled(
      elegidas.map(([clave, v]) => {
        const payload: ReglaCreate =
          por === 'cabys'
            ? { cliente_id: clienteId, cabys: clave, clasificacion: v.clasificacion, sub_clasificacion: v.sub.trim() || null, rol: null }
            : { cliente_id: clienteId, cedula: clave, clasificacion: v.clasificacion, rol };
        return crear.mutateAsync(payload);
      }),
    );
    const ok = results.filter((r) => r.status === 'fulfilled').length;
    const fail = results.length - ok;
    notifications.show({
      color: fail ? 'orange' : 'teal',
      message: `${ok} regla(s) creada(s)${fail ? `, ${fail} con error` : ''}`,
    });
    const failedKeys = new Set(
      results
        .map((r, i) => (r.status === 'rejected' ? elegidas[i][0] : null))
        .filter((k): k is string => k !== null),
    );
    setAsig((a) => Object.fromEntries(Object.entries(a).filter(([k]) => failedKeys.has(k))));
    qc.invalidateQueries({ queryKey: ['preclasificacion'] });
    qc.invalidateQueries({ queryKey: ['resumen'] });
    qc.invalidateQueries({ queryKey: ['resumen-clasificacion'] });
  }

  if (isLoading) return <Loader />;
  if (isError)
    return <Alert color="red">Error al cargar <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;
  const grupos = data ?? [];
  if (grupos.length === 0)
    return <Text c="dimmed">No hay líneas sin clasificar para este período/rol.</Text>;

  const hayAsignadas = Object.values(asig).some((v) => v.clasificacion);

  return (
    <Stack>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{por === 'cabys' ? 'CABYS' : 'Cédula'}</Table.Th>
            <Table.Th>{por === 'cabys' ? 'Detalle' : 'Proveedor'}</Table.Th>
            <Table.Th>Líneas</Table.Th>
            <Table.Th>Base</Table.Th>
            <Table.Th>Clasificación</Table.Th>
            {por === 'cabys' && <Table.Th>Sub-clasif.</Table.Th>}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {grupos.map((g) => (
            <Table.Tr key={g.clave}>
              <Table.Td>{g.clave}</Table.Td>
              <Table.Td>{g.etiqueta || '—'}</Table.Td>
              <Table.Td>{g.lineas}</Table.Td>
              <Table.Td>{formatColones(g.base)}</Table.Td>
              <Table.Td>
                <Select
                  data={CLASIFICACIONES}
                  placeholder="— elegir —"
                  value={asig[g.clave]?.clasificacion || null}
                  onChange={(v) => setClas(g.clave, v ?? '')}
                  aria-label={`Clasificación ${g.clave}`}
                  w={170}
                />
              </Table.Td>
              {por === 'cabys' && (
                <Table.Td>
                  <TextInput
                    placeholder="—"
                    value={asig[g.clave]?.sub ?? ''}
                    onChange={(e) => setSub(g.clave, e.currentTarget.value)}
                    aria-label={`Sub ${g.clave}`}
                    w={130}
                  />
                </Table.Td>
              )}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      <Group justify="flex-end">
        <Button onClick={guardar} loading={crear.isPending} disabled={!hayAsignadas}>
          Guardar asignaciones
        </Button>
      </Group>
    </Stack>
  );
}

export function PreclasificarPage() {
  const { clienteId, periodo, rol } = useSeleccion();
  if (clienteId == null || periodo == null)
    return <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>;
  return (
    <Stack>
      <Title order={2}>Preclasificar</Title>
      <Tabs defaultValue="cabys" keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="cabys">Por CABYS</Tabs.Tab>
          <Tabs.Tab value="cedula">Por proveedor</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="cabys" pt="md">
          <Panel por="cabys" clienteId={clienteId} periodo={periodo} rol={rol} />
        </Tabs.Panel>
        <Tabs.Panel value="cedula" pt="md">
          <Panel por="cedula" clienteId={clienteId} periodo={periodo} rol={rol} />
        </Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

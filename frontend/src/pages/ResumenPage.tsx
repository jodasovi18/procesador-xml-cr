import { Stack, Title, Tabs, Table, Alert, Loader, Button } from '@mantine/core';
import { useSeleccion, Rol } from '../context/SeleccionContext';
import { useResumen, useResumenClasificacion } from '../api/hooks';
import { formatColones } from '../lib/money';

function TablaCategoria({ clienteId, periodo, rol }: { clienteId: number | null; periodo: string | null; rol: Rol }) {
  const { data, isLoading, isError, refetch } = useResumen(clienteId, periodo, rol);
  if (isLoading) return <Loader />;
  if (isError) return <Alert color="red">Error al cargar el resumen <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;
  return (
    <Table striped>
      <Table.Thead><Table.Tr><Table.Th>Categoría</Table.Th><Table.Th>Base</Table.Th><Table.Th>IVA</Table.Th></Table.Tr></Table.Thead>
      <Table.Tbody>
        {Object.entries(data ?? {}).map(([cat, v]) => (
          <Table.Tr key={cat}>
            <Table.Td>{cat}</Table.Td><Table.Td>{formatColones(v.base)}</Table.Td><Table.Td>{formatColones(v.iva)}</Table.Td>
          </Table.Tr>
        ))}
      </Table.Tbody>
    </Table>
  );
}

function TablaClasificacion({ clienteId, periodo, rol }: { clienteId: number | null; periodo: string | null; rol: Rol }) {
  const { data, isLoading, isError, refetch } = useResumenClasificacion(clienteId, periodo, rol);
  if (isLoading) return <Loader />;
  if (isError) return <Alert color="red">Error al cargar la clasificación <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;
  return (
    <Table striped>
      <Table.Thead><Table.Tr><Table.Th>Clasificación</Table.Th><Table.Th>Tasa</Table.Th><Table.Th>Base</Table.Th><Table.Th>IVA</Table.Th></Table.Tr></Table.Thead>
      <Table.Tbody>
        {Object.entries(data ?? {}).flatMap(([clas, tasas]) =>
          Object.entries(tasas).map(([tasa, v]) => (
            <Table.Tr key={clas + tasa}>
              <Table.Td>{clas}</Table.Td><Table.Td>{tasa}</Table.Td>
              <Table.Td>{formatColones(v.base)}</Table.Td><Table.Td>{formatColones(v.iva)}</Table.Td>
            </Table.Tr>
          )))}
      </Table.Tbody>
    </Table>
  );
}

export function ResumenPage() {
  const { clienteId, periodo, rol } = useSeleccion();
  if (clienteId == null || periodo == null)
    return <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>;
  return (
    <Stack>
      <Title order={2}>Resumen</Title>
      <Tabs defaultValue="categoria">
        <Tabs.List>
          <Tabs.Tab value="categoria">Categoría</Tabs.Tab>
          <Tabs.Tab value="clasificacion">Clasificación</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="categoria" pt="md"><TablaCategoria clienteId={clienteId} periodo={periodo} rol={rol} /></Tabs.Panel>
        <Tabs.Panel value="clasificacion" pt="md"><TablaClasificacion clienteId={clienteId} periodo={periodo} rol={rol} /></Tabs.Panel>
      </Tabs>
    </Stack>
  );
}

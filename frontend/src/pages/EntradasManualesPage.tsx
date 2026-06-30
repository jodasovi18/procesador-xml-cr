import { useState } from 'react';
import { Table, Button, Modal, TextInput, NumberInput, Checkbox, Stack, Group, Title, Alert, Loader, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useSeleccion } from '../context/SeleccionContext';
import {
  useEntradasManuales, useCrearEntrada, useEditarEntrada, useEliminarEntrada,
  EntradaManual, EntradaManualCreate, periodoApi,
} from '../api/hooks';
import { ApiError } from '../api/client';
import { formatColones } from '../lib/money';

interface FormValues {
  descripcion: string;
  monto: number | string;
  tarifa: number | string;
  no_sujeto: boolean;
  deducible: boolean;
}
const VACIO: FormValues = { descripcion: '', monto: 0, tarifa: 0, no_sujeto: false, deducible: true };

export function EntradasManualesPage() {
  const { clienteId, periodo, rol } = useSeleccion();
  const { data, isLoading, isError, refetch } = useEntradasManuales(clienteId, periodo, rol);
  const crear = useCrearEntrada();
  const editar = useEditarEntrada();
  const eliminar = useEliminarEntrada();
  // undefined = modal cerrado; null = creando; EntradaManual = editando
  const [editando, setEditando] = useState<EntradaManual | null | undefined>(undefined);
  const [aEliminar, setAEliminar] = useState<EntradaManual | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorEliminar, setErrorEliminar] = useState<string | null>(null);
  const form = useForm<FormValues>({ initialValues: VACIO });

  function abrirNuevo() {
    setError(null);
    form.setValues(VACIO);
    setEditando(null);
  }
  function abrirEditar(e: EntradaManual) {
    setError(null);
    form.setValues({ descripcion: e.descripcion ?? '', monto: e.monto, tarifa: e.tarifa, no_sujeto: e.no_sujeto, deducible: e.deducible });
    setEditando(e);
  }
  function cerrar() {
    setEditando(undefined);
    setError(null);
    form.reset();
  }

  async function onSubmit(values: FormValues) {
    if (clienteId == null || periodo == null) return;
    setError(null);
    const payload: EntradaManualCreate = {
      cliente_id: clienteId,
      periodo: periodoApi(periodo), // YYYY-MM → YYYYMM para el backend
      rol,
      descripcion: values.descripcion.trim() || null,
      monto: String(values.monto),
      tarifa: String(values.tarifa),
      no_sujeto: values.no_sujeto,
      deducible: values.deducible,
    };
    try {
      if (editando) await editar.mutateAsync({ id: editando.id, data: payload });
      else await crear.mutateAsync(payload);
      cerrar();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  async function confirmarEliminar() {
    if (!aEliminar) return;
    setErrorEliminar(null);
    try {
      await eliminar.mutateAsync({ id: aEliminar.id });
      setAEliminar(null);
    } catch (e) {
      setErrorEliminar(e instanceof ApiError ? e.detail : 'Error al eliminar');
    }
  }

  if (clienteId == null || periodo == null)
    return <Alert color="yellow">Elegí cliente y período en la barra superior.</Alert>;
  if (isLoading) return <Loader />;
  if (isError)
    return <Alert color="red">Error al cargar <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;

  const resp = data ?? { entradas: [], total_monto: '0', total_iva: '0' };

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Entradas manuales</Title>
        <Button onClick={abrirNuevo}>Nueva entrada</Button>
      </Group>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Descripción</Table.Th>
            <Table.Th>Monto</Table.Th>
            <Table.Th>Tarifa</Table.Th>
            <Table.Th>No sujeto</Table.Th>
            <Table.Th>Deducible</Table.Th>
            <Table.Th>IVA</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {resp.entradas.map((e) => (
            <Table.Tr key={e.id}>
              <Table.Td>{e.descripcion ?? '—'}</Table.Td>
              <Table.Td>{formatColones(e.monto)}</Table.Td>
              <Table.Td>{e.tarifa}%</Table.Td>
              <Table.Td>{e.no_sujeto ? '✓' : '—'}</Table.Td>
              <Table.Td>{e.deducible ? '✓' : '—'}</Table.Td>
              <Table.Td>{formatColones(e.iva)}</Table.Td>
              <Table.Td>
                <Group gap="xs">
                  <Button variant="subtle" size="xs" onClick={() => abrirEditar(e)}>Editar</Button>
                  <Button variant="subtle" color="red" size="xs" onClick={() => { setErrorEliminar(null); setAEliminar(e); }}>Eliminar</Button>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
        <Table.Tfoot>
          <Table.Tr>
            <Table.Th>Total ({resp.entradas.length})</Table.Th>
            <Table.Th>{formatColones(resp.total_monto)}</Table.Th>
            <Table.Th />
            <Table.Th />
            <Table.Th />
            <Table.Th>{formatColones(resp.total_iva)}</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Tfoot>
      </Table>

      <Modal opened={editando !== undefined} onClose={cerrar} title={editando ? 'Editar entrada' : 'Nueva entrada'}>
        <form onSubmit={form.onSubmit(onSubmit)}>
          <Stack>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput label="Descripción" {...form.getInputProps('descripcion')} />
            <Group grow>
              <NumberInput label="Monto (₡)" min={0} decimalScale={5} {...form.getInputProps('monto')} />
              <NumberInput label="Tarifa (%)" min={0} decimalScale={4} {...form.getInputProps('tarifa')} />
            </Group>
            <Group>
              <Checkbox label="No sujeto" {...form.getInputProps('no_sujeto', { type: 'checkbox' })} />
              <Checkbox label="Deducible" {...form.getInputProps('deducible', { type: 'checkbox' })} />
            </Group>
            <Button type="submit" loading={crear.isPending || editar.isPending}>Guardar</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={aEliminar !== null} onClose={() => { setAEliminar(null); setErrorEliminar(null); }} title="Eliminar entrada">
        <Text>¿Eliminar esta entrada manual?</Text>
        {errorEliminar && <Alert color="red">{errorEliminar}</Alert>}
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setAEliminar(null)}>Cancelar</Button>
          <Button color="red" loading={eliminar.isPending} onClick={confirmarEliminar}>Eliminar</Button>
        </Group>
      </Modal>
    </Stack>
  );
}

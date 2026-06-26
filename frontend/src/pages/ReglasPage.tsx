import { useState } from 'react';
import { Table, Button, Modal, TextInput, Select, Stack, Group, Title, Alert, Loader, Text } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useSeleccion } from '../context/SeleccionContext';
import { useReglas, useCrearRegla, useEditarRegla, useEliminarRegla, Regla, ReglaCreate } from '../api/hooks';
import { ApiError } from '../api/client';

const CLASIFICACIONES = ['Compras', 'Gastos', 'Bienes de Capital', 'No Deducibles', 'Sin Clasificar'];
const ROLES = [
  { value: '', label: '— (cualquiera)' },
  { value: 'compra', label: 'compra' },
  { value: 'venta', label: 'venta' },
];

interface FormValues {
  cedula: string;
  cabys: string;
  rol: string;
  clasificacion: string;
  sub_clasificacion: string;
}

const VACIO: FormValues = { cedula: '', cabys: '', rol: '', clasificacion: 'Compras', sub_clasificacion: '' };

export function ReglasPage() {
  const { clienteId } = useSeleccion();
  const { data: reglas, isLoading, isError, refetch } = useReglas(clienteId);
  const crear = useCrearRegla();
  const editar = useEditarRegla();
  const eliminar = useEliminarRegla();
  // undefined = modal cerrado; null = creando; Regla = editando
  const [editando, setEditando] = useState<Regla | null | undefined>(undefined);
  const [aEliminar, setAEliminar] = useState<Regla | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorEliminar, setErrorEliminar] = useState<string | null>(null);
  const form = useForm<FormValues>({
    initialValues: VACIO,
    validate: {
      cedula: (v, values) =>
        !v.trim() && !values.cabys.trim() ? 'Indicá al menos cédula o CABYS' : null,
    },
  });

  function abrirNuevo() {
    setError(null);
    form.setValues(VACIO);
    setEditando(null);
  }
  function abrirEditar(r: Regla) {
    setError(null);
    form.setValues({
      cedula: r.cedula ?? '',
      cabys: r.cabys ?? '',
      rol: r.rol ?? '',
      clasificacion: r.clasificacion,
      sub_clasificacion: r.sub_clasificacion ?? '',
    });
    setEditando(r);
  }
  function cerrar() {
    setEditando(undefined);
    setError(null);
    form.reset();
  }

  async function onSubmit(values: FormValues) {
    if (clienteId == null) return;
    setError(null);
    const payload: ReglaCreate = {
      cliente_id: clienteId,
      cedula: values.cedula.trim() || null,
      cabys: values.cabys.trim() || null,
      rol: values.rol || null,
      clasificacion: values.clasificacion,
      sub_clasificacion: values.sub_clasificacion.trim() || null,
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
    if (!aEliminar || clienteId == null) return;
    setErrorEliminar(null);
    try {
      await eliminar.mutateAsync({ id: aEliminar.id, clienteId });
      setAEliminar(null);
    } catch (e) {
      setErrorEliminar(e instanceof ApiError ? e.detail : 'Error al eliminar');
    }
  }

  if (clienteId == null) return <Alert color="yellow">Elegí un cliente en la barra superior.</Alert>;
  if (isLoading) return <Loader />;
  if (isError)
    return (
      <Alert color="red">
        Error al cargar las reglas <Button size="xs" onClick={() => refetch()}>Reintentar</Button>
      </Alert>
    );

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Reglas de clasificación</Title>
        <Button onClick={abrirNuevo}>Nueva regla</Button>
      </Group>
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Cédula</Table.Th>
            <Table.Th>CABYS</Table.Th>
            <Table.Th>Rol</Table.Th>
            <Table.Th>Clasificación</Table.Th>
            <Table.Th>Sub-clasif.</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(reglas ?? []).map((r) => (
            <Table.Tr key={r.id}>
              <Table.Td>{r.cedula ?? '—'}</Table.Td>
              <Table.Td>{r.cabys ?? '—'}</Table.Td>
              <Table.Td>{r.rol ?? '—'}</Table.Td>
              <Table.Td>{r.clasificacion}</Table.Td>
              <Table.Td>{r.sub_clasificacion ?? '—'}</Table.Td>
              <Table.Td>
                <Group gap="xs">
                  <Button variant="subtle" size="xs" onClick={() => abrirEditar(r)}>Editar</Button>
                  <Button variant="subtle" color="red" size="xs" onClick={() => { setErrorEliminar(null); setAEliminar(r); }}>Eliminar</Button>
                </Group>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Modal opened={editando !== undefined} onClose={cerrar} title={editando ? 'Editar regla' : 'Nueva regla'}>
        <form onSubmit={form.onSubmit(onSubmit)}>
          <Stack>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput label="Cédula" id="regla-cedula" {...form.getInputProps('cedula')} />
            <TextInput label="CABYS" {...form.getInputProps('cabys')} />
            <Select label="Rol" data={ROLES} {...form.getInputProps('rol')} />
            <Select label="Clasificación" data={CLASIFICACIONES} {...form.getInputProps('clasificacion')} />
            <TextInput
              label="Sub-clasificación"
              description='"Combustibles" fuerza tratamiento No Sujeto'
              {...form.getInputProps('sub_clasificacion')}
            />
            <Button type="submit" loading={crear.isPending || editar.isPending}>Guardar</Button>
          </Stack>
        </form>
      </Modal>

      <Modal opened={aEliminar !== null} onClose={() => { setAEliminar(null); setErrorEliminar(null); }} title="Eliminar regla">
        <Text>¿Eliminar esta regla de clasificación?</Text>
        {errorEliminar && <Alert color="red">{errorEliminar}</Alert>}
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setAEliminar(null)}>Cancelar</Button>
          <Button color="red" loading={eliminar.isPending} onClick={confirmarEliminar}>Eliminar</Button>
        </Group>
      </Modal>
    </Stack>
  );
}

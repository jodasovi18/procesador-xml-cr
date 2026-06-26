import { useState } from 'react';
import { Table, Button, Modal, TextInput, Select, Stack, Group, Title, Alert, Loader } from '@mantine/core';
import { useForm } from '@mantine/form';
import { useClientes, useCrearCliente } from '../api/hooks';
import type { ClienteCreate } from '../api/hooks';
import { ApiError } from '../api/client';

// tipo_cedula: free string; CR values: fisica, juridica, dimex, nite
// regimen: free string; CR values: tradicional, simplificado
// (backend schema has TODO to enforce these — using sensible defaults for the UI)

export function ClientesPage() {
  const { data: clientes, isLoading, isError, refetch } = useClientes();
  const crear = useCrearCliente();
  const [abierto, setAbierto] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const form = useForm<ClienteCreate>({
    initialValues: {
      nombre: '',
      cedula: '',
      tipo_cedula: 'juridica',
      regimen: 'tradicional',
    },
  });

  async function onSubmit(values: ClienteCreate) {
    setError(null);
    try {
      await crear.mutateAsync(values);
      setAbierto(false);
      form.reset();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  if (isLoading) return <Loader />;
  if (isError)
    return (
      <Alert color="red">
        Error al cargar clientes{' '}
        <Button onClick={() => refetch()}>Reintentar</Button>
      </Alert>
    );

  return (
    <Stack>
      <Group justify="space-between">
        <Title order={2}>Clientes</Title>
        <Button onClick={() => setAbierto(true)}>Nuevo cliente</Button>
      </Group>

      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Nombre</Table.Th>
            <Table.Th>Cédula</Table.Th>
            <Table.Th>Régimen</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {(clientes ?? []).map((c) => (
            <Table.Tr key={c.id}>
              <Table.Td>{c.nombre}</Table.Td>
              <Table.Td>{c.cedula}</Table.Td>
              <Table.Td>{c.regimen}</Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>

      <Modal
        opened={abierto}
        onClose={() => { setAbierto(false); form.reset(); setError(null); }}
        title="Nuevo cliente"
        transitionProps={{ duration: 0 }}
      >
        <form onSubmit={form.onSubmit(onSubmit)}>
          <Stack>
            {error && <Alert color="red">{error}</Alert>}
            <TextInput id="cliente-nombre" label="Nombre" required {...form.getInputProps('nombre')} />
            <TextInput id="cliente-cedula" label="Cédula" required {...form.getInputProps('cedula')} />
            <Select
              label="Tipo de cédula"
              data={['fisica', 'juridica', 'dimex', 'nite']}
              {...form.getInputProps('tipo_cedula')}
            />
            <Select
              label="Régimen"
              data={['tradicional', 'simplificado']}
              {...form.getInputProps('regimen')}
            />
            <Button type="submit" loading={crear.isPending}>
              Guardar
            </Button>
          </Stack>
        </form>
      </Modal>
    </Stack>
  );
}

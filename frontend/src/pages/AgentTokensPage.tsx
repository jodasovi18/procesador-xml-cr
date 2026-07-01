import { useState } from 'react';
import { Table, Button, TextInput, Stack, Group, Title, Alert, Loader, Text, Code, Modal } from '@mantine/core';
import { useForm } from '@mantine/form';
import dayjs from 'dayjs';
import { useAgentTokens, useCrearAgentToken, useRevocarAgentToken, AgentToken } from '../api/hooks';
import { ApiError } from '../api/client';

export function AgentTokensPage() {
  const { data, isLoading, isError, refetch } = useAgentTokens();
  const crear = useCrearAgentToken();
  const revocar = useRevocarAgentToken();
  const [creadoToken, setCreadoToken] = useState<string | null>(null);
  const [aRevocar, setARevocar] = useState<AgentToken | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorRevocar, setErrorRevocar] = useState<string | null>(null);
  const form = useForm({ initialValues: { label: '' }, validate: { label: (v: string) => (v.trim() ? null : 'Requerido') } });

  async function onSubmit(values: { label: string }) {
    setError(null);
    try {
      const res = await crear.mutateAsync(values.label);
      if (res) setCreadoToken(res.token);
      form.reset();
    } catch (e) {
      setError(e instanceof ApiError ? e.detail : 'Error de conexión');
    }
  }

  async function confirmarRevocar() {
    if (!aRevocar) return;
    setErrorRevocar(null);
    try {
      await revocar.mutateAsync(aRevocar.id);
      setARevocar(null);
    } catch (e) {
      setErrorRevocar(e instanceof ApiError ? e.detail : 'Error al revocar');
    }
  }

  function copiar() {
    if (creadoToken) navigator.clipboard?.writeText(creadoToken);
  }

  if (isLoading) return <Loader />;
  if (isError)
    return <Alert color="red">Error al cargar <Button size="xs" onClick={() => refetch()}>Reintentar</Button></Alert>;
  const tokens = data ?? [];

  return (
    <Stack>
      <Title order={2}>Tokens de agente</Title>
      <form onSubmit={form.onSubmit(onSubmit)}>
        <Group align="flex-end">
          <TextInput label="Etiqueta" placeholder="Agente oficina PC-01" {...form.getInputProps('label')} />
          <Button type="submit" loading={crear.isPending}>Crear token</Button>
        </Group>
      </form>
      {error && <Alert color="red">{error}</Alert>}
      {creadoToken && (
        <Alert color="teal" title="Token creado — copialo ahora">
          <Text size="sm">No se vuelve a mostrar. Guardalo en la config del agente (token).</Text>
          <Group mt="xs">
            <Code>{creadoToken}</Code>
            <Button size="xs" onClick={copiar}>Copiar</Button>
            <Button size="xs" variant="default" onClick={() => setCreadoToken(null)}>Listo</Button>
          </Group>
        </Alert>
      )}
      <Table striped>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Etiqueta</Table.Th>
            <Table.Th>Creado</Table.Th>
            <Table.Th />
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {tokens.map((t) => (
            <Table.Tr key={t.id}>
              <Table.Td>{t.label}</Table.Td>
              <Table.Td>{dayjs(t.created_at).format('YYYY-MM-DD HH:mm')}</Table.Td>
              <Table.Td>
                <Button variant="subtle" color="red" size="xs" onClick={() => { setErrorRevocar(null); setARevocar(t); }}>Revocar</Button>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {tokens.length === 0 && <Text c="dimmed">No hay tokens creados.</Text>}

      <Modal opened={aRevocar !== null} onClose={() => { setARevocar(null); setErrorRevocar(null); }} title="Revocar token">
        <Text>¿Revocar el token "{aRevocar?.label}"? El agente que lo use dejará de funcionar.</Text>
        {errorRevocar && <Alert color="red">{errorRevocar}</Alert>}
        <Group justify="flex-end" mt="md">
          <Button variant="default" onClick={() => setARevocar(null)}>Cancelar</Button>
          <Button color="red" loading={revocar.isPending} onClick={confirmarRevocar}>Revocar</Button>
        </Group>
      </Modal>
    </Stack>
  );
}

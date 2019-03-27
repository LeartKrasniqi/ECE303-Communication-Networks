/* Leart Krasniqi
 * ECE303: Communication Networks
 * Prof. Mevawala
 * TCP Port Scanner

 * Usage: ./port_scan hostname [-p start end]
*/

/* Resources used:
 * https://stackoverflow.com/questions/4181784/how-to-set-socket-timeout-in-c-when-making-multiple-connections
 * https://www.gta.ufrj.br/ensino/eel878/sockets/sockaddr_inman.html
 * https://www.gnu.org/software/libc/manual/html_node/Host-Names.html
 * https://stackoverflow.com/questions/2597608/c-socket-connection-timeout
*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <sys/socket.h>
#include <netdb.h>
#include <ctype.h>
#include <arpa/inet.h>
#include <errno.h>
#include <time.h>
#include <sys/types.h>
#include <fcntl.h>
#define SEC 0
#define USEC 100000


int main(int argc, char **argv)
{
	switch(argc)
	{
		case 2: break;
		case 5: break;
		default: 	fprintf(stderr, "ERROR: Expected usage is:\n./port_scan hostname [-p start end]\n");
					return -1;
	}

	/* Hostname Stuff */
	struct sockaddr_in *socket_addr;	/* Socket Address */
	struct hostent *host;				/* Host */

	socket_addr = malloc(sizeof(struct sockaddr_in));
	socket_addr->sin_family = AF_INET;


	/* Check to see if hostname is already in numeric form */
	if (isdigit(argv[1][0]))
		socket_addr->sin_addr.s_addr = inet_addr(argv[1]);
	/* Otherwise use function to get hostname */
	else if ( (host = gethostbyname(argv[1])) )
		socket_addr->sin_addr = *(struct in_addr *) host->h_addr;
	else
	{
		herror(argv[1]);
		return -1;
	}

	/* Port Handling */
	int start_port;
	int end_port;

	/* Default Ports */
	if (argc == 2)
	{
		start_port = 1;
		end_port = 1024;
	}
	/* User Provided Ports */
	else
	{
		start_port = strtol(argv[3], NULL, 10);
		end_port = strtol(argv[4], NULL, 10);
		if ( (start_port < 1) || (start_port > 1024) || (end_port < 1) || (end_port > 1024) || (start_port > end_port) )
		{
			fprintf(stderr, "ERROR: Port numbers must be in the range 1 <= start <= end <= 1024 \n");
			return -1;
		}
	}

	fprintf(stdout, "Checking ports ... \n");

	/* Loop through the ports */
	for (int port = start_port; port <= end_port; port++)
	{
		/* Create (non-blocking) socket */
		int s = socket(AF_INET, SOCK_STREAM, 0);
		if (s < 0)
		{
			fprintf(stderr, "Error creating socket: %s\n", strerror(errno));
			return -1;
		}
		if (fcntl(s, F_SETFL, O_NONBLOCK) == -1)
		{
			fprintf(stderr, "Error setting the non-blocking attribute: %s\n", strerror(errno));
			return -1;
		}

		/* Update the port number */
		socket_addr->sin_port = htons(port);

		/* Get service info about port */
		struct servent *serv = malloc(sizeof(struct servent));
		serv = getservbyport(htons(port), "tcp");

		/* Connect to socket */
		connect(s, (struct sockaddr *)socket_addr, sizeof(*socket_addr));
		
		/* Timeout */
		fd_set fdset;
    	struct timeval tv;

		FD_ZERO(&fdset);
    	FD_SET(s, &fdset);
    	tv.tv_sec = SEC;             
    	tv.tv_usec = USEC;

    	if ( select(s + 1, NULL, &fdset, NULL, &tv) )
    	{
       		int so_error, len;
        	getsockopt(s, SOL_SOCKET, SO_ERROR, &so_error, (socklen_t *)&len);

        	if (so_error == 0)
        	{
        		if (serv != NULL)
        			fprintf(stdout, "Port %d is open (%s)\n", port, serv->s_name);
        		else
        			fprintf(stdout, "Port %d is open\n", port);
        	}
    	}

		/* Close Socket */
		close(s);
	}

	return 0;

}

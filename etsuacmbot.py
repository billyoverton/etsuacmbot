from ircbot import SingleServerIRCBot
from irclib import nm_to_n, nm_to_h, irc_lower, ip_numstr_to_quad, ip_quad_to_numstr, is_channel
from collections import deque

import random
import re

SERVER = "irc.freenode.net"
PORT=6667
CHANNEL = "#etsuacm"
NICK = "etsuacm_bot"
COMMAND_CHAR = '!'
HISTORY_SIZE = 10

class AcmBot(SingleServerIRCBot):

    message_history = None

    def __init__(self, channel, nickname, server, port=6667, commandCharacter='.'):
        SingleServerIRCBot.__init__(self, [(server, port)], nickname, nickname)
        self.channel = channel
        self.cmdChar = commandCharacter
        self.helpQueue = deque()
        self.message_history = []
    def on_nicknameinuse(self, c, e):
        """Adds successive underscores to the bots name if its default nick is taken."""
        c.nick(c.get_nickname() + "_")
    
    def on_welcome(self, c, e):
        """ Ran when the bot receives a welcome message from the server on connect."""
        c.join(self.channel)
        
    def on_pubmsg(self, c, e):
        """ Checks every public message to see if it is a command
        and passes it off for processing"""
        self.store_history(nm_to_n(e.source()), e.arguments()[0])
        if(e.arguments()[0][0] == self.cmdChar):
            self.process_public_command(nm_to_n(e.source()), e.arguments()[0][len(self.cmdChar):])
 
    def on_privmsg(self, c, e):
        """ Checks every private message and passes it off as a command for processing"""
        self.process_private_command(nm_to_n(e.source()), e.arguments()[0])
    
    def store_history(self, nick, message):
        if len(self.message_history) == HISTORY_SIZE:
            self.message_history.pop(0)
        self.message_history.append((nick, message))


    def process_private_command(self, nick, commandString):
        """Processes all private commands sent to the bot. The command is assumed to be the first
        value in the commandString array."""

        # Command list, both public and private.
        # key = "identifying command string sent to the bot"
        # value = "function defined to handle said command"
        #
        # All command functions take a list of strings as a single argument
        # All keys are lower case
        commands = {"purge": self.purge_queue,
                    "die": self.kill_command,
                    "help": self.add_user_to_help_queue,
                    "next": self.get_next_user_to_help,
                    "history": self.get_history
                    }
        # make sure we have something to process
        if(commandString == ''):
            return
            
        command_arguments = commandString.split()
        command = command_arguments.pop(0).lower()
        
        # delegate a command to its proper function defined in commands
        if(command in commands.keys()):
            commands[command](nick, command_arguments)
        else:
            # Send error message back to the user as a private message.
            # Avoids issues where someone is trying to figure out commands
            self.send_message(nick, "Sorry. " + command + " is not a valid command.")


    def process_public_command(self, nick, commandString):
        """Processes all public commands sent to the bot. The command is assumed to be the first
        value in the commandString array."""
        
        # Command list, both public and private.
        # key = "identifying command string sent to the bot"
        # value = "function defined to handle said command"
        #
        # All command functions take a list of strings as a single argument
        # All keys are lower case.
        commands = {"info": self.print_info,
                    "help": self.print_help,
                    "stats": self.print_stats,
                    "roll": self.roll_dice
                    }

        # make sure we have something to process
        if(commandString == ''):
            return
            
        command_arguments = commandString.split()
        command = command_arguments.pop(0).lower()
        
        # delegate a command to its proper function defined in commands
        if(command in commands.keys()):
            commands[command](nick, command_arguments)
        else:
            # Send error message back to the user as a private message.
            # Avoids issues where someone is trying to figure out commands
            self.send_message(nick, "Sorry. " + command + " is not a valid command.")
        
    def send_message(self, target, message):
        """ Sends a message to the designated target.
        
        Target can be a channel in the case of a public message
        or a Nick in the case of a private message."""
        
        assert(type(message) == type(""))
        c = self.connection
        
        for line in message.splitlines():
            c.privmsg(target, line)
            if(target == self.channel):
                self.store_history(c.get_nickname(), line)
        
    def is_user(self, nick):
        """ Returns true if the nick is a user in the channel"""
        return self.channels[self.channel].has_user(nick)   
    def is_op(self, nick):
        """ Returns true if nick is an oper in the channel"""
        return self.channels[self.channel].is_oper(nick)    
    def is_voiced(self, nick):
        """ Returns true if the nick is voiced in the channel
        
        In the case of ops. Only returns true if it saw the +v at some point"""
        return self.channels[self.channel].is_voiced(nick)
    
    ##################
    ## Public Commands
    ##################
    
    def print_info(self, nick, command_arguments):
        """ Prints information regarding the permissions and status of a given nick.
        The checked nick is the first value in command_arguments

        Results are returned to the channel."""

        assert(type(command_arguments) == type([]))
        
        if(len(command_arguments) == 1):
            nick = command_arguments[0]
            if self.is_user(nick):
                self.send_message(self.channel, nick + " is in the channel.")
                if self.is_op(nick):
                    self.send_message(self.channel, nick + " is an OP")
                if self.is_voiced(nick):
                    self.send_message(self.channel, nick + " is Voiced")
            else:
                self.send_message(self.channel, "Unknown user: " + nick)
    def get_history(self, nick, command_arguments):
        for sender, message in self.message_history:
            self.send_message(nick, sender + ": " + message)
    def print_stats(self, nick, command_arguments):
        """ Prints status information about the bot

        Results are returned to the channel."""

        self.send_message(self.channel,"Number of people in the help queue: " + str(len(self.helpQueue)))

    def roll_dice(self, nick, command_arguments):
        dice_regex = re.compile("([0-9]*)d([1-9][0-9]*)([\+-][0-9]+)?")

        roll_string = "1d20"
        
        if len(command_arguments) >= 1:
            roll_string = command_arguments[0]

        reg_match = dice_regex.match(roll_string)
        if reg_match is None:
            self.send_message(self.channel, nick + ": Invalid dice string.")
            return

        dice_parts = [x for x in reg_match.groups()]
        
        if(dice_parts[0] is ''): dice_parts[0] = '1'
        if(dice_parts[2] is None): dice_parts[2] = '0'
       

        num_of_dice = int(dice_parts[0])
        type_of_dice = int(dice_parts[1])
        dice_modifier = int(dice_parts[2])

        roll = 0
        for i in range(num_of_dice):
            roll = roll +  random.randint(1, type_of_dice)

        roll = roll + dice_modifier

        self.send_message(self.channel, nick + ": (" + roll_string + ") = " + str(roll))
    def print_help(self, nick, command_arguments):
        """ Prints help infomration regarding the bots usage.

        Results are returned to the calling user."""
        helpMSG = """ETSU HELP Desk Bot
==================
Public commands are said directly in the #etsuacm channel.

Valid Public Commands:
    !info <nick> - Prints information about a user. 
    !help - Prints this help dialog.
    !stats - Prints status information about the help desk and this bot
    !roll <diceString> - Rolls dice according to the diceString (default 1d20) 
==================
Private Commands are sent as private messages to the help bot.

Valid Private Command:
    history - Prints the last few messages said in the channel.
    help <question> - Adds your name and question to the help queue.
    next - Gets the next vaild person out of the help queue. (Voiced Only)
    purge - Removes everybody from the help queue. (OP Only)
    die - Removes the bot from the channel. (OP only)"""
        
        self.send_message(nick, helpMSG)
                
    #####################
    ## Private Commands
    #####################

    def purge_queue(self, nick, command_arguments):
        """Removes all users from the help queue.

        Requires OP permissions to run."""
        if self.is_user(nick) and self.is_op(nick):
            self.helpQueue.clear()
            self.send_message(nick, "The help queue has been purged")
        else:
            self.send_message(nick, "You do not have permission to run this command.")

    def kill_command(self, nick, command_arguments):
        """Forces the script to close.

        Requires OP permissions to run."""
        if self.is_user(nick) and self.is_op(nick):
            self.die()
        else:
            self.send_message(nick, "You do not have permission to run this command.")

    def add_user_to_help_queue(self, nick, command_arguments):
        """
        Adds a user and a question to the help queue.
        Users in the queue are unique, so only one question per nick in the queue.

        Sends a alert message to all help desk members when the question is accepted.

        Requires the calling user be in the channel."""
        if (len(command_arguments) >= 1) and self.is_user(nick):
            for qnick, question in self.helpQueue:
                if qnick == nick:
                    self.send_message(nick, "You can only have one question in the queue at a time.\nPlease wait for a volunteer to help you.")
                    return
            
            self.helpQueue.append((nick, ' '.join(command_arguments)))
            self.send_message(nick, "You question has been added to the help queue.")
            self.send_message(nick, "A volunteer will contact you as soon as they can.")
            self.send_message(nick, "There are currently " + str(len(self.helpQueue)) + " person(s) in the queue.")

            #notify all voiced members of a person in the queue
            for voicedNick in self.channels[self.channel].voiced():
                    self.send_message(voicedNick, "A person has been added to the help queue.")
            
            #notify all oped members of a person in the queue
            #for opedNick in self.channels[self.channel].opers():
            #        self.send_message(opedNick, "A person has been added to the help queue.")

    def get_next_user_to_help(self, nick, command_arguments):
        """ Returns the next user from the help queue and their question.

        Requires VOICED or OP permissions to run.
        """
        if self.is_voiced(nick) or self.is_op(nick):
            
            #Search queue for the next user that is still in the channel
            foundNextNick = False
            user, question = None, None
            while(not foundNextNick):
                if(len(self.helpQueue) == 0):
                    self.send_message(nick, "There is no one in the help queue at this time.")
                    return

                user, question = self.helpQueue.popleft()
                if self.is_user(user):
                    foundNextNick = True

            self.send_message(nick, "Next User: " + user)
            self.send_message(nick, " Question: " + question)
            self.send_message(nick, "Please contact the user via private message to start helping them.")
        else:
            self.send_message(nick, "You don't have premission to use this command.")

        
def main():
    bot = AcmBot(CHANNEL, NICK, SERVER, PORT, COMMAND_CHAR)
    bot.start()

if __name__ == "__main__":
    main()
